# 📧 GitHub 批量邀请用户工具

> 🚀 **自动化邀请管理！** 通过脚本批量邀请用户加入 GitHub 组织或企业，支持邮箱和用户名两种邀请方式。

## 🌟 功能特性

- 📬 **邮箱邀请**：通过邮箱地址邀请用户
- 👤 **用户名邀请**：通过 GitHub 用户名邀请用户  
- 🏢 **组织邀请**：邀请用户加入 GitHub 组织
- 🏛️ **企业邀请**：邀请用户加入 GitHub 企业
- 📊 **批量处理**：从文本文件读取多个用户信息
- ⚡ **自动化**：减少手动邀请的重复工作

## 📁 文件说明

| 文件名 | 功能描述 | 适用场景 |
|--------|---------|---------|
| `invitemember-org-email.py` | 通过邮箱邀请用户加入组织 | 新用户或未知 GitHub 用户名的邀请 |
| `invitemember-org-login.py` | 通过用户名邀请用户加入组织 | 已知 GitHub 用户名的邀请 |
| `invitemember-ent-email.py` | 通过邮箱邀请用户加入企业 | 企业级用户管理 |
| `usermails.txt` | 邮箱地址列表文件 | 存储待邀请用户的邮箱地址 |
| `usernames.txt` | 用户名列表文件 | 存储待邀请用户的 GitHub 用户名 |

## 🔧 使用前准备

### 1. 获取访问令牌
从 [GitHub Settings > Tokens](https://github.com/settings/tokens) 生成个人访问令牌（Personal Access Token）：

- **组织邀请**：需要 `admin:org` 权限
- **企业邀请**：需要 `admin:enterprise` 权限

### 2. 安装依赖
```bash
pip install requests
```

### 3. 准备用户列表文件
- **邮箱邀请**：编辑 `usermails.txt`，每行一个邮箱地址
- **用户名邀请**：编辑 `usernames.txt`，每行一个 GitHub 用户名

## 📖 使用方法

### 方案一：通过邮箱邀请用户加入组织

```python
# 编辑 invitemember-org-email.py
token = "your_personal_access_token"  # 你的 Personal Access Token
organization = "your_organization_name"  # 你的组织名
filename = "usermails.txt"  # 邮箱列表文件

# 运行脚本
python invitemember-org-email.py
```

### 方案二：通过用户名邀请用户加入组织

```python
# 编辑 invitemember-org-login.py
token = "your_personal_access_token"  # 你的 Personal Access Token
organization = "your_organization_name"  # 你的组织名
filename = "usernames.txt"  # 用户名列表文件

# 运行脚本
python invitemember-org-login.py
```

## 📋 配置示例

### usermails.txt 格式
```
user1@example.com
user2@company.com
user3@domain.org
```

### usernames.txt 格式
```
githubuser1
githubuser2
githubuser3
```

## ⚠️ 注意事项

- 🔐 **权限要求**：确保访问令牌具有足够的权限
- 📧 **邮箱有效性**：确保邮箱地址格式正确且有效
- 👤 **用户名存在性**：通过用户名邀请时，确保用户名存在
- ⏱️ **API 限制**：遵守 GitHub API 的速率限制
- 🔒 **令牌安全**：不要将访问令牌提交到代码仓库

## 🐛 常见问题

### Q: 邀请失败怎么办？
- 检查访问令牌权限
- 确认组织/企业名称正确
- 验证用户邮箱或用户名格式

### Q: 如何查看邀请状态？
- 在组织设置中查看待处理的邀请
- 脚本会输出每个邀请的结果状态

### Q: 可以邀请到特定团队吗？
- 当前脚本邀请到组织级别
- 可以修改脚本添加团队邀请功能

## 🔗 相关链接

- [GitHub Organizations API](https://docs.github.com/en/rest/orgs/members)
- [GitHub Enterprise API](https://docs.github.com/en/rest/enterprise-admin)
- [Personal Access Tokens](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/creating-a-personal-access-token)

---

> 💡 **提示**：建议在正式环境使用前，先在测试组织中验证脚本功能或用少量用户进行测试。