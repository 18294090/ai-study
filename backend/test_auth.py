#!/usr/bin/env python3
"""
测试认证流程的脚本
"""
import asyncio
import httpx
import json

BASE_URL = "http://localhost:8000"

async def test_auth():
    """测试认证流程"""
    async with httpx.AsyncClient() as client:
        print("=== 测试认证流程 ===\n")

        # 1. 测试健康检查（公开路由）
        print("1. 测试健康检查...")
        try:
            response = await client.get(f"{BASE_URL}/health")
            print(f"   状态码: {response.status_code}")
            print(f"   响应: {response.json()}")
        except Exception as e:
            print(f"   错误: {e}")

        # 2. 测试公开题目列表
        print("\n2. 测试公开题目列表...")
        try:
            response = await client.get(f"{BASE_URL}/api/v1/questions/public")
            print(f"   状态码: {response.status_code}")
            if response.status_code == 200:
                data = response.json()
                print(f"   题目数量: {len(data) if isinstance(data, list) else 'N/A'}")
            else:
                print(f"   错误: {response.text}")
        except Exception as e:
            print(f"   错误: {e}")

        # 3. 测试需要认证的路由（应该返回401）
        print("\n3. 测试需要认证的路由...")
        try:
            response = await client.get(f"{BASE_URL}/api/v1/questions/")
            print(f"   状态码: {response.status_code}")
            if response.status_code == 401:
                print("   ✅ 正确返回401（需要认证）")
            else:
                print(f"   意外状态码: {response.status_code}")
                print(f"   响应: {response.text}")
        except Exception as e:
            print(f"   错误: {e}")

        # 4. 测试用户注册
        print("\n4. 测试用户注册...")
        try:
            user_data = {
                "email": "test@example.com",
                "username": "testuser",
                "password": "testpass123"
            }
            response = await client.post(
                f"{BASE_URL}/api/v1/auth/register",
                json=user_data,
                headers={"Content-Type": "application/json"}
            )
            print(f"   状态码: {response.status_code}")
            if response.status_code == 201:
                print("   ✅ 用户注册成功")
            elif response.status_code == 400:
                print("   用户已存在，使用现有用户")
            else:
                print(f"   错误: {response.text}")
        except Exception as e:
            print(f"   错误: {e}")

        # 5. 测试用户登录
        print("\n5. 测试用户登录...")
        try:
            login_data = {
                "username": "test@example.com",
                "password": "testpass123"
            }
            response = await client.post(
                f"{BASE_URL}/api/v1/auth/login",
                data=login_data,
                headers={"Content-Type": "application/x-www-form-urlencoded"}
            )
            print(f"   状态码: {response.status_code}")
            if response.status_code == 200:
                token_data = response.json()
                access_token = token_data.get("access_token")
                print("   ✅ 登录成功，获取到token")
                print(f"   Token: {access_token[:50]}...")

                # 6. 使用token测试认证路由
                print("\n6. 使用token测试认证路由...")
                headers = {"Authorization": f"Bearer {access_token}"}
                response = await client.get(f"{BASE_URL}/api/v1/questions/", headers=headers)
                print(f"   状态码: {response.status_code}")
                if response.status_code == 200:
                    data = response.json()
                    print(f"   ✅ 认证成功，获取到 {len(data) if isinstance(data, list) else 0} 条题目")
                else:
                    print(f"   认证失败: {response.text}")

                # 7. 测试获取用户信息
                print("\n7. 测试获取用户信息...")
                response = await client.get(f"{BASE_URL}/api/v1/auth/me", headers=headers)
                print(f"   状态码: {response.status_code}")
                if response.status_code == 200:
                    user_info = response.json()
                    print(f"   ✅ 获取用户信息成功: {user_info.get('username')}")
                else:
                    print(f"   错误: {response.text}")

            else:
                print(f"   登录失败: {response.text}")
        except Exception as e:
            print(f"   错误: {e}")

        # 8. 测试批量导入（现在应该有权限）
                print("\n8. 测试批量导入...")
                try:
                    # 创建一个简单的测试文件
                    import tempfile
                    import os
                    
                    # 创建一个简单的文本文件作为测试
                    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
                        f.write("这是一个测试文件")
                        test_file_path = f.name
                    
                    # 读取文件内容
                    with open(test_file_path, 'rb') as f:
                        file_content = f.read()
                    
                    # 上传文件测试（注意：这只是测试权限，不是真正的文件处理）
                    files = {'file': ('test.txt', file_content, 'text/plain')}
                    response = await client.post(
                        f"{BASE_URL}/api/v1/questions/batch-import",
                        files=files,
                        headers={"Authorization": f"Bearer {access_token}"}
                    )
                    print(f"   状态码: {response.status_code}")
                    if response.status_code == 200:
                        print("   ✅ 批量导入权限测试成功")
                        result = response.json()
                        print(f"   响应: {result}")
                    else:
                        print(f"   错误: {response.text}")
                    
                    # 清理临时文件
                    os.unlink(test_file_path)
                    
                except Exception as e:
                    print(f"   错误: {response.text}")

if __name__ == "__main__":
    asyncio.run(test_auth())