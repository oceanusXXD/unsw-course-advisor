"""
Vector Store Builder for UNSW Course Data
[已修改] 使用本地 SentenceTransformer 和优化的分块策略
"""

import json
import os
from pathlib import Path
from typing import List, Dict, Any, Optional, Generator
from dataclasses import dataclass
import chromadb
from chromadb.config import Settings
# from openai import OpenAI # 不再需要
# from dotenv import load_dotenv # 不再需要 (除非你有其他key)
from tqdm import tqdm
# import time # 不再需要 time.sleep
from sentence_transformers import SentenceTransformer
import torch
import pickle
import re

@dataclass
class EmbeddingDocument:
    """Document to be embedded"""
    id: str  # Unique ID
    text: str  # Text to embed
    metadata: Dict[str, Any]  # Metadata for filtering
    source_type: str  # "course", "major", "requirement_group", "prerequisite"


class VectorStoreBuilder:
    """Build vector store from UNSW course data"""

    # 修复: __init__ 现在正确设置了所有必需的类变量
    def __init__(self,
                 model_name: str = 'BAAI/bge-small-en-v1.5',
                 batch_size: int = 32,
                 collection_name: str = "unsw_courses"):
        """
        [已修改] 初始化本地 SentenceTransformer 和配置
        """
        self.collection_name = collection_name
        self.batch_size = batch_size
        
        print(f"Loading local embedding model: {model_name}...")
        device_to_use = 'cuda' if torch.cuda.is_available() else 'cpu'
        print(f"Using device: {device_to_use}")

        self.model = SentenceTransformer(model_name, device=device_to_use)
        print("[OK] Local model loaded.")
        
        # 获取模型的维度
        self.dimensions = self.model.get_sentence_embedding_dimension()
        print(f"Model dimensions: {self.dimensions}")

        self.chroma_client = None
        self.collection = None

    # 修复: _get_embeddings 已被合并到 _batch_embed 中，可以删除
    # def _get_embeddings(self, ...):
    #     ...

    # 修复: _batch_embed 现在极其高效
    def _batch_embed(self, texts: List[str]) -> List[List[float]]:
        """
        [已优化] 使用 SentenceTransformer 一次性高效编码所有文本。
        """
        print(f"Generating embeddings for {len(texts)} documents (model batch_size={self.batch_size})...")
        
        # self.model.encode() 会自动处理批量和显示进度条
        embeddings = self.model.encode(
            texts,
            batch_size=self.batch_size,
            show_progress_bar=True
        )
        
        print("\n[OK] Embeddings generated.")
        return [emb.tolist() for emb in embeddings]

    def initialize_chroma(self, persist_directory: str):
        """Initialize Chroma client and collection"""
        persist_path = Path(persist_directory)
        persist_path.mkdir(parents=True, exist_ok=True)
        
        print(f"Initializing Chroma at {persist_path}...")
        
        self.chroma_client = chromadb.PersistentClient(
            path=str(persist_path),
            settings=Settings(
                anonymized_telemetry=False,
                allow_reset=True
            )
        )
        
        # Delete existing collection if exists
        try:
            self.chroma_client.delete_collection(name=self.collection_name)
            print(f"  Deleted existing collection '{self.collection_name}'")
        except:
            pass
        
        # Create new collection
        self.collection = self.chroma_client.create_collection(
            name=self.collection_name,
            metadata={"description": "UNSW course data with embeddings"}
        )
        
        print(f"  [OK] Created collection '{self.collection_name}'")

    def _clean_html(self, raw_html: str) -> str:
        """Helper to clean HTML tags and excessive whitespace"""
        if not raw_html:
            return ""
        clean_text = re.sub('<.*?>', ' ', raw_html) # 用空格替换标签
        clean_text = re.sub(r'\s+', ' ', clean_text) # 合并多个空格
        return clean_text.strip()

    def _parse_prereq_to_text(self, prereq: Optional[Dict]) -> str:
        """[新] 辅助函数：将 parsed_prerequisite JSON 转换为可读文本"""
        if prereq is None:
            return ""
        
        op = prereq.get("op")
        args = prereq.get("args")

        if op == "AND":
            return " and ".join([f"({self._parse_prereq_to_text(arg)})" for arg in args])
        elif op == "OR":
            return " or ".join([f"({self._parse_prereq_to_text(arg)})" for arg in args])
        elif prereq.get("type") == "course":
            return prereq.get("code", "")
        elif prereq.get("type") == "uoc":
            return f"{prereq.get('uoc', '0')} UOC"
        elif prereq.get("type") == "coreq_of":
             return f"corequisite of {prereq.get('code', '')}"
        elif prereq.get("type") == "prereq_of":
             return f"prerequisite of {prereq.get('code', '')}"
        
        # 捕获其他未知类型
        return json.dumps(prereq, ensure_ascii=False)


    def _get_level_from_url(self, url: str) -> str:
        """从 URL 中提取 'ug' 或 'pg'"""
        if "postgraduate" in url:
            return "PG" # 研究生
        if "undergraduate" in url:
            return "UG" # 本科
        return "UNK" # 未知

    def load_course_data(self, compiled_data_path: str) -> Generator[EmbeddingDocument, None, None]:
        """
        [已优化] 加载课程数据，并为每个课程创建多个“子文档”(分块)。
        [!!] 已修复：使用 (code + level) 作为唯一 ID
        [!!] 已修复：将 offering_terms 列表转换为字符串
        """
        print("\nLoading course data (with chunking)...")
        
        # [!!] 修复：使用清洗后的 "compiled_data_cleaned.json" [!!]
        # (确保你已经运行了 clean_compiled_data.py)
        cleaned_data_path = Path(compiled_data_path).with_name("compiled_data.json")
        if not cleaned_data_path.exists():
            print(f"[ERR] 错误: 未找到清洗后的文件: {cleaned_data_path}")
            print("  > 请先运行 RAG_database/clean_compiled_data.py")
            return
            
        print(f"  > 正在从 {cleaned_data_path.name} 加载...")
        with open(cleaned_data_path, 'r', encoding='utf-8') as f:
            courses = json.load(f)
        
        doc_count = 0
        
        for course in tqdm(courses, desc="Processing courses"):
            course_code = course.get("course_code", "")
            if not course_code:
                continue

            course_url = course.get("url", "")
            level_tag = self._get_level_from_url(course_url)
            unique_course_id = f"{course_code}_{level_tag}"
            
            # (注意：因为我们用了 _cleaned.json, 理论上不再需要 'seen_ids' 检查)

            course_name = (course.get("raw_entry") or {}).get("title", "")
            overview = self._clean_html(course.get("overview", ""))
            
            # 1. [父文档] - 概述 (Overview Chunk)
            if overview:
                text_parts = [f"Course Code: {course_code} ({level_tag})"]
                if course_name:
                    text_parts.append(f"Course Name: {course_name}")
                text_parts.append(f"Overview: {overview}")
                
                text = ". ".join(text_parts)
                
                # --- [!!] 就在这里！这是你的修复 [!!] ---
                terms_list = course.get("parsed_terms", [])
                terms_string = ", ".join(terms_list) # e.g., "T1, T2"
                # --- 修复结束 ---

                metadata = {
                    "course_code": course_code,
                    "course_name": course_name,
                    "study_level": level_tag, 
                    "source_type": "course",
                    "level": next((int(c) for c in course_code if c.isdigit()), 0),
                    "credit_points": str((course.get("raw_entry") or {}).get("uoc", "6")),
                    "offering_terms": terms_string, # [!!] 使用修复后的字符串
                    "url": course_url
                }
                
                doc = EmbeddingDocument(
                    id=f"course_{unique_course_id}",
                    text=text,
                    metadata=metadata,
                    source_type="course"
                )
                yield doc
                doc_count += 1

            # 2. [子文档] - 先修课程 (Prerequisite Chunk)
            prereq_json = course.get("parsed_prerequisite")
            prereq_text = self._parse_prereq_to_text(prereq_json)
            if prereq_text:
                text = f"Prerequisites for {course_code} ({level_tag}): {prereq_text}."
                metadata = {
                    "course_code": course_code, "course_name": course_name,
                    "study_level": level_tag, "source_type": "prerequisite",
                    "url": course_url
                }
                yield EmbeddingDocument(
                    id=f"prereq_{unique_course_id}",
                    text=text,
                    metadata=metadata,
                    source_type="prerequisite"
                )
                doc_count += 1
            
            # 3. [子文档] - 并修课程 (Corequisite Chunk)
            coreq_json = course.get("parsed_corequisite")
            coreq_text = self._parse_prereq_to_text(coreq_json)
            if coreq_text:
                text = f"Corequisites for {course_code} ({level_tag}): {coreq_text}."
                metadata = {
                    "course_code": course_code, "course_name": course_name,
                    "study_level": level_tag, "source_type": "corequisite",
                    "url": course_url
                }
                yield EmbeddingDocument(
                    id=f"coreq_{unique_course_id}",
                    text=text,
                    metadata=metadata,
                    source_type="corequisite"
                )
                doc_count += 1

            # 4. [子文档] - 不兼容课程 (Incompatible Chunk)
            incomp_json = course.get("parsed_incompatible")
            incomp_text = self._parse_prereq_to_text(incomp_json)
            if incomp_text:
                text = f"Incompatible courses for {course_code} ({level_tag}): {incomp_text}."
                metadata = {
                    "course_code": course_code, "course_name": course_name,
                    "study_level": level_tag, "source_type": "incompatible",
                    "url": course_url
                }
                yield EmbeddingDocument(
                    id=f"incomp_{unique_course_id}",
                    text=text,
                    metadata=metadata,
                    source_type="incompatible"
                )
                doc_count += 1

            # 5. [子文档] - 注册限制 (Enrolment Chunk)
            enrol_text = self._clean_html((course.get("raw_entry") or {}).get("additional_enrolment_constraints", ""))
            if enrol_text:
                text = f"Enrolment constraints for {course_code} ({level_tag}): {enrol_text}."
                metadata = {
                    "course_code": course_code, "course_name": course_name,
                    "study_level": level_tag, "source_type": "enrolment",
                    "url": course_url
                }
                yield EmbeddingDocument(
                    id=f"enrol_{unique_course_id}",
                    text=text,
                    metadata=metadata,
                    source_type="enrolment"
                )
                doc_count += 1
        
        print(f"  [OK] Prepared {doc_count} total course documents (chunks)")

    # (load_major_data 和 load_requirement_group_data 保持不变, 但也改为了 yield)
    def load_major_data(self, graduation_req_dir: str) -> Generator[EmbeddingDocument, None, None]:
        print("\nLoading major data...")
        grad_req_path = Path(graduation_req_dir)
        doc_count = 0
        for json_file in tqdm(list(grad_req_path.glob("cleaned_*.json")), desc="Processing majors"):
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    major_data = json.load(f)
                
                major_code = major_data.get("code", "")
                if not major_code: continue
                
                text_parts = [f"Major Code: {major_code}"]
                title = major_data.get("title", "")
                if title: text_parts.append(f"Major Title: {title}")
                
                description = self._clean_html(major_data.get("description", ""))
                structure_summary = self._clean_html(major_data.get("structure_summary", ""))
                
                if description: text_parts.append(f"Description: {description[:500]}")
                if structure_summary: text_parts.append(f"Structure: {structure_summary}")
                
                text = ". ".join(text_parts)
                metadata = {
                    "major_code": major_code,
                    "major_title": title,
                    "source_type": "major",
                    "faculty": major_data.get("faculty", ""),
                    "school": major_data.get("school", ""),
                    "total_uoc": major_data.get("total_credit_points", ""),
                    "study_level": major_data.get("study_level", "")
                }
                yield EmbeddingDocument(
                    id=f"major_{major_code}",
                    text=text,
                    metadata=metadata,
                    source_type="major"
                )
                doc_count += 1
            except Exception as e:
                print(f"  Error processing {json_file.name}: {e}")
        print(f"  [OK] Prepared {doc_count} major documents")

    def load_requirement_group_data(self, graduation_req_dir: str) -> Generator[EmbeddingDocument, None, None]:
        print("\nLoading requirement group data...")
        grad_req_path = Path(graduation_req_dir)
        doc_count = 0
        for json_file in tqdm(list(grad_req_path.glob("cleaned_*.json")), desc="Processing requirement groups"):
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    major_data = json.load(f)
                
                major_code = major_data.get("code", "")
                curriculum = major_data.get("curriculum_structure", {})
                requirement_groups = curriculum.get("requirement_groups", [])
                
                for group in requirement_groups:
                    group_title = group.get("title", "")
                    if not group_title: continue
                    
                    text_parts = [f"Requirement Group: {group_title}", f"Major: {major_code}"]
                    description = self._clean_html(group.get("description", ""))
                    if description: text_parts.append(f"Description: {description}")
                    
                    group_type = group.get("vertical_grouping_label", "")
                    if group_type: text_parts.append(f"Type: {group_type}")
                    
                    courses = group.get("courses", [])
                    if courses:
                        course_codes = [c.get("code", "") for c in courses[:10]]
                        text_parts.append(f"Includes courses: {', '.join(course_codes)}")
                    
                    text = ". ".join(text_parts)
                    group_id = f"{major_code}_{group_title.replace(' ', '_')}"
                    
                    metadata = {
                        "group_id": group_id,
                        "major_code": major_code,
                        "group_title": group_title,
                        "source_type": "requirement_group",
                        "group_type": group_type,
                        "required_uoc": group.get("credit_points", ""),
                        "course_count": len(courses)
                    }
                    yield EmbeddingDocument(
                        id=f"req_group_{group_id}",
                        text=text,
                        metadata=metadata,
                        source_type="requirement_group"
                    )
                    doc_count += 1
            except Exception as e:
                print(f"  Error processing {json_file.name}: {e}")
        print(f"  [OK] Prepared {doc_count} requirement group documents")

    def add_documents_to_collection(self, documents: List[EmbeddingDocument]):
        """
        [FIXED]
        Add documents to Chroma collection in batches to avoid internal limits.
        """
        if not self.collection:
            raise RuntimeError("Collection not initialized. Call initialize_chroma() first.")
        
        if not documents:
            print("  > No documents to add, skipping.")
            return

        print(f"\nAdding {len(documents)} documents to collection in batches...")
        
        # 1. Prepare all data first (this part is fine)
        ids = [doc.id for doc in documents]
        texts = [doc.text for doc in documents]
        metadatas = [doc.metadata for doc in documents]
        
        # 2. Generate all embeddings first (this part is fine and efficient)
        print("Generating all embeddings first...")
        embeddings = self._batch_embed(texts)
        
        chroma_batch_size = 4096 
        total_added = 0
        
        print(f"Adding to Chroma collection in batches of {chroma_batch_size}...")
        for i in tqdm(range(0, len(documents), chroma_batch_size), desc="Adding batches to Chroma"):
            # Slice all lists for the current batch
            batch_ids = ids[i:i + chroma_batch_size]
            batch_texts = texts[i:i + chroma_batch_size]
            batch_metadatas = metadatas[i:i + chroma_batch_size]
            batch_embeddings = embeddings[i:i + chroma_batch_size]
            
            try:
                # Add just this batch
                self.collection.add(
                    ids=batch_ids,
                    embeddings=batch_embeddings,
                    documents=batch_texts,
                    metadatas=batch_metadatas
                )
                total_added += len(batch_ids)
            except Exception as e:
                print(f"\nError adding batch starting at index {i}: {e}")
                print(f"  > Skipping this batch of {len(batch_ids)} documents.")

        print(f"\n  [OK] Added {total_added} / {len(documents)} documents to Chroma.")

    def build_vector_store(self,
                           compiled_data_path: str,
                           graduation_req_dir: str,
                           persist_directory: str):
        """
        Build complete vector store
        """
        print("="*80)
        print("Building Vector Store")
        print("="*80)
        
        self.initialize_chroma(persist_directory)
        
        # 修复: 将生成器转换为列表以进行批量添加
        course_docs = list(self.load_course_data(compiled_data_path))
        major_docs = list(self.load_major_data(graduation_req_dir))
        req_group_docs = list(self.load_requirement_group_data(graduation_req_dir))

        all_docs = course_docs + major_docs + req_group_docs
        
        self.add_documents_to_collection(all_docs)
        
        print("\n" + "="*80)
        print("Vector Store Statistics")
        print("="*80)
        print(f"Collection name: {self.collection_name}")
        print(f"Total documents: {self.collection.count()}")
        print(f"  Course Chunks: {len(course_docs)}")
        print(f"  Major Chunks: {len(major_docs)}")
        print(f"  Requirement Group Chunks: {len(req_group_docs)}")
        print(f"\nPersisted to: {persist_directory}")


def main():
    """Build vector store"""
    
    # 修复: 本地模型不需要 API keys
    # load_dotenv()
    # API_KEY = os.getenv("DASHSCOPE_API_KEY")
    # BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    # MODEL_NAME = "text-embedding-v3" # (旧)
    
    # 修复: 本地模型的配置
    MODEL_NAME = 'BAAI/bge-small-en-v1.5' # <--- 切换到 large 版本
    # BATCH_SIZE 应该根据你的 VRAM/RAM 调整
    BATCH_SIZE = 32 # (SentenceTransformer 内部的批次大小)
    COLLECTION_NAME = "unsw_courses"
    
    # Paths
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    
    compiled_data_path = project_root / "course_data" / "compiled_course_data" / "compiled_data.json"
    graduation_req_dir = project_root / "course_data" / "cleaned_graduation_requirements"
    persist_directory = project_root / "course_data" / "vector_store"
    
    print("="*80)
    print("UNSW Course Vector Store Builder")
    print("="*80)
    print(f"Project root: {project_root}")
    print(f"Compiled data: {compiled_data_path}")
    print(f"Graduation requirements: {graduation_req_dir}")
    print(f"Output: {persist_directory}")
    print(f"\nEmbedding model: {MODEL_NAME}")
    print(f"Batch size: {BATCH_SIZE}\n")
    
    if not compiled_data_path.exists():
        print(f"[ERR] Compiled data not found: {compiled_data_path}")
        return
    
    if not graduation_req_dir.exists():
        print(f"[ERR] Graduation requirements not found: {graduation_req_dir}")
        return
    
    # 修复: 使用新的 __init__ 签名
    builder = VectorStoreBuilder(
        model_name=MODEL_NAME,
        batch_size=BATCH_SIZE,
        collection_name=COLLECTION_NAME
    )
    
    builder.build_vector_store(
        compiled_data_path=str(compiled_data_path),
        graduation_req_dir=str(graduation_req_dir),
        persist_directory=str(persist_directory)
    )
    
    print("\n" + "="*80)
    print("[OK] Vector Store Build Complete!")
    print("="*80)


if __name__ == "__main__":
    main()