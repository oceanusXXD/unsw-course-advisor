import requests
import json

# 基础配置
BASE_URL = "http://localhost:8000"
HEADERS = {"Content-Type": "application/json"}

def activate_license(user_id, device_id):
    """激活许可证"""
    url = f"{BASE_URL}/api/activate_license/"
    data = {
        "user_id": user_id,
        "device_id": device_id
    }
    response = requests.post(url, headers=HEADERS, data=json.dumps(data))
    return response

def validate_license(user_id, license_key, user_key=None):
    """验证许可证"""
    url = f"{BASE_URL}/api/validate_license/"
    data = {
        "user_id": user_id,
        "license_key": license_key
    }
    if user_key:  # 如果提供了user_key，加入请求数据
        data["user_key"] = user_key
    response = requests.post(url, headers=HEADERS, data=json.dumps(data))
    return response

if __name__ == "__main__":
    # 测试数据
    test_user = "admin1"
    test_device = "device-xx"

    # 1. 先激活许可证
    print("激活许可证...")
    activate_resp = activate_license(test_user, test_device)
    print(f"激活响应: {activate_resp.status_code}, {activate_resp.text}")

    # 从激活响应中提取license_key和user_key
    if activate_resp.status_code == 200:
        activate_data = activate_resp.json()
        license_key = activate_data.get("license_key")
        user_key = activate_data.get("user_key")
        
        # 2. 然后验证许可证（带上user_key）
        print("\n验证许可证...")
        validate_resp = validate_license(test_user, license_key, user_key)
        print(f"验证响应: {validate_resp.status_code}, {validate_resp.text}")
    else:
        print("激活失败，跳过验证")