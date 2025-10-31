#!/usr/bin/env python3
"""
GitHub Enterprise Team 成员同步脚本
根据 JSON 配置文件同步 Enterprise Team 成员
"""

import json
import os
import sys
import requests
from datetime import datetime
from typing import Dict, List, Set, Tuple, Optional


class GitHubEnterpriseTeamSync:
    """GitHub Enterprise Team 成员同步器"""
    
    def __init__(self, token: str, enterprise: str):
        """
        初始化同步器
        
        Args:
            token: GitHub Personal Access Token (需要 admin:enterprise 权限)
            enterprise: Enterprise slug 名称
        """
        self.token = token
        self.enterprise = enterprise
        self.base_url = "https://api.github.com"
        self.graphql_url = "https://api.github.com/graphql"
        self.headers = {
            "Accept": "application/vnd.github+json",
            "Authorization": f"token {token}",
            "X-GitHub-Api-Version": "2022-11-28"
        }
        
        # 获取 Enterprise Node ID (用于 GraphQL)
        self.enterprise_id = None
        self._fetch_enterprise_id()
        
        # 报告数据
        self.report = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "enterprise": enterprise,
            "teams": []
        }
    
    def _make_request(self, method: str, url: str, **kwargs) -> Tuple[bool, Dict]:
        """
        发起 HTTP 请求的通用方法
        
        Args:
            method: HTTP 方法 (GET, POST, PUT, DELETE)
            url: 请求 URL
            **kwargs: 其他请求参数
            
        Returns:
            (成功标志, 响应的 JSON 数据)
        """
        try:
            response = requests.request(method, url, headers=self.headers, **kwargs)
            response.raise_for_status()
            return True, response.json() if response.text else {}
        except requests.exceptions.RequestException as e:
            error_msg = str(e)
            if hasattr(e.response, 'text'):
                error_msg = f"{error_msg} - {e.response.text}"
            return False, {"error": error_msg}
    
    def _graphql_request(self, query: str, variables: Optional[Dict] = None) -> Dict:
        """
        发起 GraphQL 请求
        
        Args:
            query: GraphQL 查询或突变语句
            variables: GraphQL 变量
            
        Returns:
            响应的数据
            
        Raises:
            Exception: GraphQL 请求失败或返回错误
        """
        try:
            payload = {"query": query}
            if variables:
                payload["variables"] = variables
            
            response = requests.post(
                self.graphql_url,
                headers=self.headers,
                json=payload
            )
            response.raise_for_status()
            result = response.json()
            
            if "errors" in result:
                raise Exception(f"GraphQL 错误: {result['errors']}")
            
            return result.get("data", {})
        except requests.exceptions.RequestException as e:
            print(f"GraphQL 请求失败: {e}")
            if hasattr(e.response, 'text'):
                print(f"响应内容: {e.response.text}")
            raise
    
    def _fetch_enterprise_id(self):
        """获取 Enterprise 的 Node ID (用于 GraphQL 操作)"""
        query = """
        query($slug: String!) {
            enterprise(slug: $slug) {
                id
                name
            }
        }
        """
        try:
            data = self._graphql_request(query, {"slug": self.enterprise})
            if data and "enterprise" in data:
                self.enterprise_id = data["enterprise"]["id"]
                print(f"✓ 获取 Enterprise ID: {self.enterprise_id}")
            else:
                print(f"⚠ 警告: 无法获取 Enterprise ID")
        except Exception as e:
            print(f"⚠ 警告: 获取 Enterprise ID 失败: {e}")
            print("  GraphQL 邀请功能将不可用")
    
    def get_user_email(self, username: str) -> Optional[str]:
        """
        通过用户名获取用户的主邮箱地址
        
        Args:
            username: GitHub 用户名
            
        Returns:
            用户邮箱，如果无法获取则返回 None
        """
        query = """
        query($login: String!) {
            user(login: $login) {
                email
                login
            }
        }
        """
        try:
            data = self._graphql_request(query, {"login": username})
            if data and "user" in data and data["user"]:
                return data["user"].get("email")
            return None
        except Exception as e:
            print(f"  ⚠️ 无法获取用户 {username} 的邮箱: {e}")
            return None
    
    def get_team_members(self, team_id: int) -> Tuple[bool, Dict[str, str]]:
        """
        获取 Team 的所有成员及其邮箱
        
        Args:
            team_id: Team 的 ID
            
        Returns:
            (成功标志, 成员字典 {username: email} 或错误信息)
        """
        url = f"{self.base_url}/enterprises/{self.enterprise}/teams/{team_id}/memberships"
        members = {}
        page = 1
        
        while True:
            success, data = self._make_request(
                "GET", 
                f"{url}?per_page=100&page={page}"
            )
            
            if not success:
                return False, {}
            
            if not data:
                break
            
            # 获取每个成员的邮箱
            for member in data:
                username = member["login"]
                email = self.get_user_email(username)
                members[username] = email if email else ""
            
            if len(data) < 100:
                break
            page += 1
        
        return True, members
    
    def get_enterprise_members(self) -> Tuple[bool, Set[str]]:
        """
        获取 Enterprise 的所有成员 (使用 GraphQL API)
        
        Returns:
            (成功标志, 成员用户名集合)
        """
        if not self.enterprise_id:
            print(f"  ⚠️  无法获取企业成员列表: Enterprise ID 未获取")
            return False, set()
        
        query = """
        query($enterpriseId: ID!, $cursor: String) {
            node(id: $enterpriseId) {
                ... on Enterprise {
                    members(first: 100, after: $cursor) {
                        pageInfo {
                            hasNextPage
                            endCursor
                        }
                        edges {
                            node {
                                ... on User {
                                    login
                                }
                                ... on EnterpriseUserAccount {
                                    login
                                }
                            }
                        }
                    }
                }
            }
        }
        """
        
        members = set()
        cursor = None
        
        try:
            while True:
                variables = {"enterpriseId": self.enterprise_id}
                if cursor:
                    variables["cursor"] = cursor
                
                data = self._graphql_request(query, variables)
                
                if not data or "node" not in data or not data["node"]:
                    break
                
                members_data = data["node"].get("members", {})
                edges = members_data.get("edges", [])
                
                for edge in edges:
                    node = edge.get("node", {})
                    login = node.get("login")
                    if login:
                        members.add(login)
                
                page_info = members_data.get("pageInfo", {})
                if not page_info.get("hasNextPage"):
                    break
                
                cursor = page_info.get("endCursor")
            
            return True, members
        except Exception as e:
            print(f"  ⚠️  无法获取企业成员列表: {e}")
            return False, set()
    
    def get_pending_invitations(self) -> Dict[str, Dict]:
        """
        获取 Enterprise 的待处理邀请
        
        注意: GitHub API 目前不提供查询待处理邀请的功能
        因此此方法返回空字典，脚本会在每次运行时尝试发送邀请
        如果邀请已存在，GraphQL API 会返回错误但不会重复发送
        
        Returns:
            字典，key 为邮箱，value 为邀请信息 (当前始终返回空字典)
        """
        # GitHub API 暂不支持查询待处理邀请
        # 可通过 GitHub Web UI 查看: https://github.com/enterprises/{enterprise}/people/pending_invitations
        return {}
    
    def get_user_email(self, username: str) -> Optional[str]:
        """
        获取 GitHub 用户的公开邮箱
        
        Args:
            username: GitHub 用户名
            
        Returns:
            用户邮箱，如果无法获取则返回 None
        """
        url = f"{self.base_url}/users/{username}"
        
        try:
            success, data = self._make_request("GET", url)
            if success and data.get("email"):
                return data["email"]
        except Exception as e:
            pass
        
        return None
    
    def add_member_to_team(self, team_id: int, username: str) -> Tuple[bool, str]:
        """
        添加成员到 Team
        
        Args:
            team_id: Team 的 ID
            username: 用户名
            
        Returns:
            (成功标志, 消息)
        """
        url = f"{self.base_url}/enterprises/{self.enterprise}/teams/{team_id}/memberships/{username}"
        success, data = self._make_request("PUT", url)
        
        if success:
            return True, "已添加到 Team"
        else:
            return False, f"添加失败: {data}"
    
    def remove_member_from_team(self, team_id: int, username: str) -> Tuple[bool, str]:
        """
        从 Team 移除成员
        
        Args:
            team_id: Team 的 ID
            username: 用户名
            
        Returns:
            (成功标志, 消息)
        """
        url = f"{self.base_url}/enterprises/{self.enterprise}/teams/{team_id}/memberships/{username}"
        success, data = self._make_request("DELETE", url)
        
        if success:
            return True, "已从 Team 移除"
        else:
            return False, f"移除失败: {data}"
    
    def invite_to_enterprise(self, email: str) -> Tuple[bool, str]:
        """
        邀请用户加入 Enterprise (使用 GraphQL API)
        
        Args:
            email: 用户邮箱
            
        Returns:
            (成功标志, 消息)
        """
        if not self.enterprise_id:
            return False, "无法邀请: Enterprise ID 未获取"
        
        mutation = """
        mutation($enterpriseId: ID!, $email: String!) {
            inviteEnterpriseMember(input: {enterpriseId: $enterpriseId, email: $email}) {
                invitation {
                    id
                    email
                }
            }
        }
        """
        
        try:
            variables = {
                "enterpriseId": self.enterprise_id,
                "email": email
            }
            data = self._graphql_request(mutation, variables)
            
            if data and "inviteEnterpriseMember" in data:
                invitation = data["inviteEnterpriseMember"]["invitation"]
                return True, f"已发送邀请 (ID: {invitation['id']})"
            else:
                return False, "响应格式不正确"
        except Exception as e:
            return False, f"邀请失败: {str(e)}"
    
    def is_email(self, identifier: str) -> bool:
        """判断是否为邮箱地址"""
        return "@" in identifier
    
    def get_team_by_name(self, team_name: str) -> Tuple[bool, Dict]:
        """
        通过 team 名称获取 team 信息
        
        Args:
            team_name: Team 名称
            
        Returns:
            (成功标志, team 信息字典或错误信息)
        """
        url = f"{self.base_url}/enterprises/{self.enterprise}/teams"
        page = 1
        
        while True:
            success, data = self._make_request(
                "GET",
                f"{url}?per_page=100&page={page}"
            )
            
            if not success:
                return False, f"无法获取 teams 列表: {data}"
            
            if not data:
                break
            
            # 查找匹配的 team
            for team in data:
                if team["name"].lower() == team_name.lower():
                    return True, {"id": team["id"], "slug": team["slug"]}
            
            if len(data) < 100:
                break
            page += 1
        
        return False, f"未找到名为 '{team_name}' 的 team"
    
    def sync_team(self, team_name: str, target_members: List[str], team_id: int = None, team_slug: str = None) -> Dict:
        """
        同步单个 Team 的成员
        
        Args:
            team_name: Team 名称
            target_members: 目标成员列表
            team_id: Team 的 ID (可选，如果不提供会自动查找)
            team_slug: Team 的 slug (可选，用于显示)
            
        Returns:
            同步报告
        """
        # 如果没有提供 ID，尝试通过名称查找
        if not team_id:
            print(f"\n🔍 正在查找 Team: {team_name}...")
            success, result = self.get_team_by_name(team_name)
            if not success:
                print(f"  ❌ {result}")
                return {
                    "name": team_name,
                    "slug": None,
                    "added": [],
                    "removed": [],
                    "invited": [],
                    "errors": [result]
                }
            team_id = result["id"]
            team_slug = result["slug"]
            print(f"  ✅ 找到 Team (ID: {team_id}, slug: {team_slug})")
        
        print(f"\n{'='*60}")
        print(f"正在同步 Team: {team_name} (ID: {team_id}, slug: {team_slug})")
        print(f"{'='*60}")
        
        team_report = {
            "name": team_name,
            "id": team_id,
            "slug": team_slug,
            "added": [],
            "removed": [],
            "invited": [],
            "errors": []
        }
        
        # 1. 获取当前 Team 成员
        print("\n📋 获取当前 Team 成员...")
        success, current_members = self.get_team_members(team_id)
        
        if not success:
            error_msg = f"无法获取 Team 成员列表: {current_members}"
            print(f"  ❌ {error_msg}")
            team_report["errors"].append(error_msg)
            return team_report
        
        print(f"  ✅ 当前成员数: {len(current_members)}")
        if current_members:
            print(f"     {', '.join(current_members)}")
        
        # 2. 获取企业成员列表
        print("\n📋 获取 Enterprise 成员列表...")
        success, enterprise_members = self.get_enterprise_members()
        
        if success:
            print(f"  ✅ Enterprise 成员数: {len(enterprise_members)}")
        else:
            print(f"  ⚠️  无法获取 Enterprise 成员列表，将尝试直接添加")
            enterprise_members = set()
        
        # 2.5 获取待处理的邀请
        print("\n📋 获取待处理邀请...")
        pending_invitations = self.get_pending_invitations()
        
        if pending_invitations:
            print(f"  ✅ 待处理邀请数: {len(pending_invitations)}")
            for email, info in pending_invitations.items():
                print(f"     📧 {email} (邀请者: {info['inviter']}, 创建时间: {info['created_at'][:10]})")
        else:
            print(f"  ℹ️  无待处理邀请")
        
        # 3. 支持成员为对象（含 email/username），同步时优先用 email 邀请，增删都用 username 作为唯一标识
        # current_members: {username: email}
        current_identifiers = {}  # username_lower -> username
        for username in current_members.keys():
            current_identifiers[username.lower()] = username

        # 目标成员处理：支持字符串或对象
        target_identifiers = {}  # username_lower -> {'username':..., 'email':...}
        for member in target_members:
            if isinstance(member, dict):
                username = member.get('username', '').strip()
                email = member.get('email', '').strip()
                if username:
                    target_identifiers[username.lower()] = {'username': username, 'email': email}
            elif isinstance(member, str):
                if self.is_email(member):
                    username = member.split('@')[0]
                    target_identifiers[username.lower()] = {'username': username, 'email': member}
                else:
                    target_identifiers[member.lower()] = {'username': member, 'email': ''}

        current_keys = set(current_identifiers.keys())
        target_keys = set(target_identifiers.keys())

        to_add = target_keys - current_keys
        to_remove = current_keys - target_keys

        print(f"\n🔍 差异分析 (基于用户名):")
        print(f"  • 当前成员: {len(current_keys)}")
        print(f"  • 目标成员: {len(target_keys)}")
        print(f"  • 需要添加: {len(to_add)}")
        if to_add:
            for k in to_add:
                info = target_identifiers[k]
                print(f"    + {info['username']} ({info['email']})" if info['email'] else f"    + {info['username']}")
        print(f"  • 需要移除: {len(to_remove)}")
        if to_remove:
            for k in to_remove:
                username = current_identifiers[k]
                print(f"    - {username}")
        
        # 4. 添加成员
        if to_add:
            print(f"\n➕ 添加成员到 Team...")
            for key in to_add:
                info = target_identifiers[key]
                username = info['username']
                email = info['email']
                # 优先用 email 邀请
                if email:
                    if key in pending_invitations:
                        msg = f"{email} 已有待处理邀请，等待用户接受"
                        print(f"  ⏳ {msg}")
                        team_report["invited"].append(email)
                    else:
                        print(f"  📧 {email}: 发送 Enterprise 邀请...")
                        success, message = self.invite_to_enterprise(email)
                        if success:
                            print(f"     ✅ {message} (等待用户接受)")
                            team_report["invited"].append(email)
                        else:
                            print(f"     ❌ {message}")
                            team_report["errors"].append(f"{email}: {message}")
                else:
                    # 没有 email，直接用用户名加 team
                    success, message = self.add_member_to_team(team_id, username)
                    if success:
                        print(f"  ✅ {username}: {message}")
                        team_report["added"].append(username)
                    else:
                        # 添加失败，检查原因
                        if "cannot be found in the enterprise" in str(message).lower():
                            if key in pending_invitations:
                                msg = f"{username} ({key}) 已有待处理邀请，等待用户接受"
                                print(f"  ⏳ {msg}")
                                team_report["invited"].append(f"{username} ({key})")
                            else:
                                print(f"  📧 {username} 不在 Enterprise，发送邀请到 {email or username}...")
                                inv_success, inv_message = self.invite_to_enterprise(email or username)
                                if inv_success:
                                    print(f"     ✅ {inv_message} (等待用户接受)")
                                    team_report["invited"].append(f"{username} ({email or username})")
                                else:
                                    print(f"     ❌ {inv_message}")
                                    team_report["errors"].append(f"{username}: 邀请失败 - {inv_message}")
                        else:
                            print(f"  ❌ {username}: {message}")
                            team_report["errors"].append(f"{username}: {message}")
        
        # 5. 移除成员
        if to_remove:
            print(f"\n➖ 从 Team 移除成员...")
            for key in to_remove:
                username = current_identifiers[key]
                success, message = self.remove_member_from_team(team_id, username)
                if success:
                    print(f"  ✅ {username}: {message}")
                    team_report["removed"].append(username)
                else:
                    print(f"  ❌ {username}: {message}")
                    team_report["errors"].append(f"{username}: {message}")
        
        return team_report
    
    def sync_from_config(self, config_file: str):
        """
        从配置文件同步所有 Teams
        
        Args:
            config_file: JSON 配置文件路径
        """
        # 读取配置文件
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
        except Exception as e:
            print(f"❌ 读取配置文件失败: {e}")
            sys.exit(1)
        
        # 验证配置
        if config.get("enterprise") != self.enterprise:
            print(f"⚠️  配置文件中的 enterprise ({config.get('enterprise')}) 与初始化不一致 ({self.enterprise})")
        
        teams = config.get("teams", [])
        if not teams:
            print("⚠️  配置文件中没有 teams")
            return
        
        print(f"\n🚀 开始同步 Enterprise: {self.enterprise}")
        print(f"📝 共需处理 {len(teams)} 个 Team(s)")
        
        # 同步每个 Team
        for team in teams:
            team_name = team.get("name")
            members = team.get("members", [])
            team_id = team.get("id")  # 可选的 team ID
            team_slug = team.get("slug")  # 可选的 slug
            
            if not team_name:
                print("⚠️  跳过没有名称的 team")
                continue
            
            team_report = self.sync_team(team_name, members, team_id, team_slug)
            self.report["teams"].append(team_report)
        
        # 生成报告
        self.generate_report()
    
    def generate_report(self):
        """生成并输出同步报告"""
        print(f"\n\n{'='*60}")
        print("📊 同步报告")
        print(f"{'='*60}")
        print(f"时间: {self.report['timestamp']}")
        print(f"Enterprise: {self.report['enterprise']}")
        print(f"{'='*60}\n")
        
        report_lines = []
        report_lines.append("=" * 60)
        report_lines.append("GitHub Enterprise Team 成员同步报告")
        report_lines.append("=" * 60)
        report_lines.append(f"时间: {self.report['timestamp']}")
        report_lines.append(f"Enterprise: {self.report['enterprise']}")
        report_lines.append("=" * 60)
        report_lines.append("")
        
        for team_report in self.report["teams"]:
            team_name = team_report["name"]
            print(f"Team: {team_name}")
            report_lines.append(f"Team: {team_name}")
            report_lines.append("-" * 60)
            
            # 成功添加的成员
            if team_report["added"]:
                print(f"\n  ✅ 成功添加到 Team ({len(team_report['added'])} 人):")
                report_lines.append(f"\n✅ 成功添加到 Team ({len(team_report['added'])} 人):")
                for member in team_report["added"]:
                    print(f"     • {member}")
                    report_lines.append(f"  • {member}")
            
            # 发送邀请的成员
            if team_report["invited"]:
                print(f"\n  📧 已发送 Enterprise 邀请 ({len(team_report['invited'])} 人):")
                print(f"     (这些用户需要先接受邀请加入 Enterprise)")
                report_lines.append(f"\n📧 已发送 Enterprise 邀请 ({len(team_report['invited'])} 人):")
                report_lines.append("  (这些用户需要先接受邀请加入 Enterprise)")
                for member in team_report["invited"]:
                    print(f"     • {member}")
                    report_lines.append(f"  • {member}")
            
            # 移除的成员
            if team_report["removed"]:
                print(f"\n  ➖ 从 Team 移除 ({len(team_report['removed'])} 人):")
                report_lines.append(f"\n➖ 从 Team 移除 ({len(team_report['removed'])} 人):")
                for member in team_report["removed"]:
                    print(f"     • {member}")
                    report_lines.append(f"  • {member}")
            
            # 错误
            if team_report["errors"]:
                print(f"\n  ❌ 错误 ({len(team_report['errors'])} 个):")
                report_lines.append(f"\n❌ 错误 ({len(team_report['errors'])} 个):")
                for error in team_report["errors"]:
                    print(f"     • {error}")
                    report_lines.append(f"  • {error}")
            
            print("")
            report_lines.append("")
            report_lines.append("")
        
        # 保存报告到文件
        report_file = "sync_report.txt"
        try:
            with open(report_file, 'w', encoding='utf-8') as f:
                f.write('\n'.join(report_lines))
            print(f"📄 报告已保存到: {report_file}")
        except Exception as e:
            print(f"⚠️  保存报告失败: {e}")


def main():
    """主函数"""
    # 从环境变量或参数获取配置
    token = os.environ.get("GITHUB_TOKEN","xxx")
    config_file = os.environ.get("CONFIG_FILE", "config.json")
    
    # 命令行参数
    if len(sys.argv) > 1:
        config_file = sys.argv[1]
    if len(sys.argv) > 2:
        token = sys.argv[2]
    
    if not token:
        print("❌ 错误: 未提供 GitHub Token")
        print("使用方法:")
        print("  1. 设置环境变量: export GITHUB_TOKEN=your_token")
        print("  2. 命令行参数: python sync_team.py config.json your_token")
        sys.exit(1)
    
    if not os.path.exists(config_file):
        print(f"❌ 错误: 配置文件不存在: {config_file}")
        sys.exit(1)
    
    # 读取配置文件获取 enterprise
    try:
        with open(config_file, 'r', encoding='utf-8') as f:
            config = json.load(f)
        enterprise = config.get("enterprise")
        if not enterprise:
            print("❌ 错误: 配置文件中缺少 'enterprise' 字段")
            sys.exit(1)
    except Exception as e:
        print(f"❌ 读取配置文件失败: {e}")
        sys.exit(1)
    
    # 创建同步器并执行
    syncer = GitHubEnterpriseTeamSync(token, enterprise)
    syncer.sync_from_config(config_file)
    # test =syncer.add_member_to_team("test", "nikawang")


if __name__ == "__main__":
    main()
