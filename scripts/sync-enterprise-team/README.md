# GitHub Enterprise Team 成员同步脚本

自动同步 GitHub Enterprise Team 成员的 Python 脚本。根据 JSON 配置文件中的成员列表，自动添加或移除 Team 成员。

## 功能特性

✅ **自动对比差异**: 对比当前 Team 成员和目标成员列表，找出需要添加和移除的成员  
✅ **智能处理**: 检查用户是否在 Enterprise 中，自动发送邀请或直接添加  
✅ **批量管理**: 支持一次性管理多个 Teams  
✅ **详细报告**: 生成完整的操作报告，记录所有变更  
✅ **错误处理**: 完善的错误处理和友好的提示信息

## 工作流程

```
1. 读取配置文件 (config.json)
   ↓
2. 获取当前 Team 成员列表
   ↓
3. 对比目标成员列表，找出差异
   ↓
4. 处理需要添加的成员:
   • 如果是邮箱 → 发送 Enterprise 邀请
   • 如果是用户名 → 检查是否在 Enterprise
     - 在 Enterprise → 直接添加到 Team
     - 不在 Enterprise → 报告错误
   ↓
5. 移除不在目标列表的成员
   ↓
6. 生成操作报告
```

## 安装依赖

```bash
pip install requests
```

## 配置文件格式


创建 `config.json` 文件，支持如下两种格式：

**1. 简单格式（兼容旧版）**

```json
{
  "enterprise": "your-enterprise-name",
  "teams": [
    {
      "name": "team-name-1",
      "members": [
        "username1",
        "username2",
        "user3@example.com"
      ]
    }
  ]
}
```

**2. 推荐格式（支持对象，含 email/username）**

```json
{
  "enterprise": "your-enterprise-name",
  "teams": [
    {
      "name": "team-name-1",
      "members": [
        {"email": "user1@example.com", "username": "username1"},
        {"email": "user2@example.com", "username": "username2"}
      ]
    }
  ]
}
```

### 配置说明


- **enterprise**: Enterprise 的 slug 名称
- **teams**: Teams 数组，每个 Team 包含:
  - **name**: Team 名称（必需）
  - **id**: Team ID（可选，如不提供会自动查找）
  - **slug**: Team slug（可选，仅用于显示）
  - **members**: 成员列表，支持以下两种格式：
    - ✅ **推荐**: 对象格式 `{"email": "xxx", "username": "xxx"}`，会优先用 email 邀请，不在 Enterprise 的用户会自动发送邀请
    - 兼容字符串格式：GitHub 用户名或邮箱（如 `octocat` 或 `user@example.com`）

> **建议**：如有邮箱，推荐用对象格式，email 字段用于自动邀请，username 字段用于团队管理。

## 使用方法

### 方法 1: 使用环境变量

```bash
# 设置 GitHub Token
export GITHUB_TOKEN="ghp_your_token_here"

# 运行脚本
python sync_team.py config.json
```

### 方法 2: 命令行参数

```bash
python sync_team.py config.json ghp_your_token_here
```

### 方法 3: 直接在脚本中运行

```bash
# 默认读取当前目录的 config.json
GITHUB_TOKEN="ghp_your_token_here" python sync_team.py
```

## GitHub Token 权限要求

需要创建一个 **Classic Personal Access Token**，包含以下权限：

- ✅ `admin:enterprise` - 管理 Enterprise teams 和成员
- ✅ `read:enterprise` - 读取 Enterprise 信息

⚠️ **注意**: Fine-grained tokens 和 GitHub App tokens 不支持 Enterprise Teams API。

### 创建 Token 步骤

1. 访问 https://github.com/settings/tokens
2. 点击 "Generate new token" → "Generate new token (classic)"
3. 选择 `admin:enterprise` 权限
4. 生成并复制 token

## 输出报告

脚本执行完成后会生成两份报告：

### 1. 控制台输出

实时显示同步过程和结果

### 2. 文件报告 (`sync_report.txt`)

保存完整的操作报告，包括：
- ✅ 成功添加到 Team 的成员
- 📧 已发送 Enterprise 邀请的成员
- ➖ 从 Team 移除的成员
- ❌ 操作失败的错误信息

## 示例

### 示例配置文件

```json
{
  "enterprise": "testfortest",
  "teams": [
    {
      "name": "test",
      "members": [
        "octocat",
        "github-user",
        "newuser@example.com"
      ]
    }
  ]
}
```

### 示例输出

```
🚀 开始同步 Enterprise: testfortest
📝 共需处理 1 个 Team(s)

============================================================
正在同步 Team: test (slug: ent:test)
============================================================

📋 获取当前 Team 成员...
  ✅ 当前成员数: 1
     octocat

📋 获取 Enterprise 成员列表...
  ✅ Enterprise 成员数: 5

🔍 差异分析:
  • 需要添加的用户名: 1
    github-user
  • 需要处理的邮箱: 1
    newuser@example.com
  • 需要移除: 0

➕ 添加成员到 Team...
  ✅ github-user: 已添加到 Team
  📧 newuser@example.com: 发送 Enterprise 邀请...
     ✅ 已发送邀请 (用户接受后需手动添加到 Team)

============================================================
📊 同步报告
============================================================
时间: 2025-10-31 10:30:00
Enterprise: testfortest
============================================================

Team: test
------------------------------------------------------------

  ✅ 成功添加到 Team (1 人):
     • github-user

  📧 已发送 Enterprise 邀请 (1 人):
     (这些用户需要先接受邀请加入 Enterprise)
     • newuser@example.com

📄 报告已保存到: sync_report.txt
```

## 注意事项

1. **Team 识别**: 脚本会自动通过 team 名称查找对应的 team ID 和 slug
2. **使用用户名**: **强烈建议使用 GitHub 用户名**而不是邮箱，因为 Enterprise 邀请 API 可能不可用
3. **权限要求**: 确保 Token 有 `admin:enterprise` 权限
4. **API 限制**: GitHub API 有速率限制，大量操作时注意间隔
5. **成员必须在 Enterprise**: 用户必须已经是 Enterprise 成员才能添加到 Team

## 常见问题

### Q: 提示 "无法获取 Team 成员列表"

A: 检查：
- Token 是否有正确的权限 (`admin:enterprise`)
- Team 名称和 slug 是否正确
- 是否使用 Classic Token (不是 fine-grained token)

### Q: 为什么不能使用邮箱地址？

A: Enterprise 邀请功能需通过 GraphQL API（`inviteEnterpriseMember` mutation）实现，且需要有足够的权限。部分企业环境可能受限。建议：
1. 在 GitHub Enterprise 页面手动邀请用户加入
2. 用户接受邀请后，在配置文件中使用其 GitHub 用户名
3. 运行脚本将用户添加到相应的 Teams

### Q: 如何测试脚本

A: 建议先在测试 Enterprise 和 Team 上测试：
1. 创建测试配置文件，只包含少量成员
2. 运行脚本观察输出
3. 检查 GitHub 上的实际变更
4. 确认无误后再应用到生产环境

## API 参考

脚本使用的 GitHub Enterprise Teams API:

- [List enterprise teams](https://docs.github.com/en/rest/enterprise-teams/enterprise-teams#list-enterprise-teams)
- [Get enterprise team members](https://docs.github.com/en/rest/enterprise-teams/members)
- [Add/Remove team membership](https://docs.github.com/en/rest/enterprise-teams/members)

## 许可证

MIT License
