import requests

# 配置
token = "xxx"  # 将值替换为您的 Personal Access Token
organization = "xxxx"  # 将值替换为您的组织名
filename = "usermails.txt"  # 假设这个文件包含的是 GitHub 用户名
# team_slug="team1"
# 从文本文件中读取 GitHub 用户名
with open(filename, "r") as file:
    usernames = [username.strip() for username in file.readlines()]

# 根据 API 要求设置请求头
headers = {
    "Accept": "application/vnd.github+json",
    "Authorization": f"token {token}",
}

api_url = f"https://api.github.com/orgs/{organization}/invitations"

# 为每个用户名发送邀请
for username in usernames:
    try:
        # 首先获取用户的 GitHub 用户ID
        user_response = requests.get(f"https://api.github.com/users/{username}", headers=headers)
        if user_response.status_code == 200:
            user_id = user_response.json()['id']
            # 使用用户ID邀请用户加入组织
            data = {"invitee_id": user_id}
            response = requests.post(api_url, json=data, headers=headers)

            if response.status_code == 201:
                print(f"Invitation sent to {username}.")
            else:
                print(f"Failed to send an invitation to {username}.")
                print("Response:", response.json())
        else:
            print(f"Failed to retrieve user ID for {username}.")
            print("Response:", user_response.json())
    except Exception as e:
        print(f"Error occurred while inviting {username}: {str(e)}")
