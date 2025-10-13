# 项目技术使用介绍

## 爬虫
- 爬取handbook资料，分为课程资料以及毕业要求
- 课程资料
    - 爬取大专业code如COMP，然后直接爬静态html解析，爬到全部课程代码
    - html爬不到的查dom更新前调用的api，直接访问做获取详细课程资料
- 毕业要求
    - 先爬大专业里的方向，如COMPIH，由于html无爬取数据，并且加载没调api，用仿造console的方式调用__NEXT_DATA___获取页面更新资料
    - 解析出来清洗，把id，key之类无用的清洗掉
- 爬虫部分做了并发，延时与重试，随机 User-Agent，防止访问过快forbidden，使用随机 UA、随机 Referer进行访问
---
## RAG
- 用阿里embedding模型以及huggingface上最常用的小模型进行embedding
- 两个爬取的数据分别做了向量化，然后做了重排和并行检索
- 优化了chunk
---
## Langgraph
- 基础模型调用
- 用flash模型进行智能路由，plus和max模型做交替响应请求，首词延时比全部max低
- 做了阈值判断来调用rag，并且对rag返回内容总结和验证，用flash模型
- 低分检索结果不做prompt，由大模型直接返回，或者是用固定模板返回
---
## Django
- 做了流输出和数据库缓存
---
## 前端
- 目前用streamlit做了简易的展示
- 后期改React优化
---
## Chrome插件
- 阈值调用，携带记忆自动选课（还没做）
- 登录账号获取数据，排除干扰项
---
## Docker/RPC/Redis/React/接本地模型或其他api格式
- 还没做