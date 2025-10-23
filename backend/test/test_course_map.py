import requests

def test_get_course_map():
    # 测试基础用例
    base_url = "http://localhost:8000/api/accounts/get_course/"
    
    # 测试用例1: 正常请求
    print("测试用例1: 正常请求")
    params = {
        "keys": "COMP9101,GSOE9011",
    }
    response = requests.get(base_url, params=params)
    print(f"状态码: {response.status_code}")
    print(f"响应数据: {response.json()}")
    print("\n")
    
    # 测试用例2: 带学期过滤
    print("测试用例2: 带学期过滤(T2)")
    params = {
        "keys": "COMP9101,GSOE9011",
        "term": "T2"
    }
    response = requests.get(base_url, params=params)
    print(f"状态码: {response.status_code}")
    print(f"响应数据: {response.json()}")
    print("\n")
    
    # 测试用例3: 空keys参数
    print("测试用例3: 空keys参数")
    params = {
        "keys": "",
    }
    response = requests.get(base_url, params=params)
    print(f"状态码: {response.status_code}")
    print(f"响应数据: {response.json()}")
    print("\n")
    
    # 测试用例4: 不存在的课程代码
    print("测试用例4: 不存在的课程代码")
    params = {
        "keys": "NOT_EXIST",
    }
    response = requests.get(base_url, params=params)
    print(f"状态码: {response.status_code}")
    print(f"响应数据: {response.json()}")
    print("\n")

if __name__ == "__main__":
    test_get_course_map()