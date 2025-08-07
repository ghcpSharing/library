import requests

# 配置
token = "xxxx"  # 将值替换为您的 Personal Access Token
filename = "usermails.txt"

GITHUB_ENTERPRISE_API="https://api.github.com/enterprises"

# 设置你的GitHub企业版的名称
ENTERPRISE="xxx"




# 从文本文件中读取电子邮件地址
with open(filename, "r") as file:
    email_addresses = [email.strip() for email in file.readlines()]

# 根据 API 要求设置请求头
headers = {
    "Accept": "application/vnd.github+json",
    "Authorization": f"token {token}",
}

api_url = f"{GITHUB_ENTERPRISE_API}/{ENTERPRISE}/invitations"

# 为每个用户名发送邀请
for email in email_addresses:
    try:
        data = {"email": email}
        response = requests.post(api_url, json=data, headers=headers)

        if response.status_code == 201:
            print(f"Invitation sent to {email}.")
        else:
            print(f"Failed to send an invitation to {email}.")
            print("Response:", response.json())
    except Exception as e:
        print(f"Error occurred while inviting {email}: {str(e)}")