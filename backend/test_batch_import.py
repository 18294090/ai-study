#!/usr/bin/env python3
"""
测试批量导入权限的脚本
"""
import asyncio
import httpx

BASE_URL = "http://localhost:8000"

async def test_batch_import():
    """测试批量导入权限"""
    async with httpx.AsyncClient() as client:
        print("=== 测试批量导入权限 ===\n")

        # 1. 用户登录获取token
        print("1. 用户登录...")
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

        if response.status_code != 200:
            print(f"   登录失败: {response.text}")
            return

        token_data = response.json()
        access_token = token_data.get("access_token")
        print("   ✅ 登录成功，获取到token")
        # 2. 测试批量导入权限
        print("\n2. 测试批量导入权限...")
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

            # 上传文件测试
            files = {'file': ('test.txt', file_content, 'text/plain')}
            headers = {"Authorization": f"Bearer {access_token}"}

            response = await client.post(
                f"{BASE_URL}/api/v1/questions/batch-import",
                files=files,
                headers=headers
            )
            print(f"   状态码: {response.status_code}")
            if response.status_code == 200:
                print("   ✅ 批量导入权限测试成功")
                result = response.json()
                print(f"   响应: {result}")
            elif response.status_code == 403:
                print("   ❌ 权限不足 (403 Forbidden)")
                print(f"   错误详情: {response.text}")
            else:
                print(f"   其他错误: {response.text}")

            # 清理临时文件
            os.unlink(test_file_path)

        except Exception as e:
            print(f"   错误: {e}")

if __name__ == "__main__":
    asyncio.run(test_batch_import())