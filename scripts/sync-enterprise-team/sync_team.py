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
                import json
                print(f"  [DEBUG] GraphQL 完整错误响应: {json.dumps(result, ensure_ascii=False, indent=2)}")
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
        获取 Enterprise 的待处理邀请 (使用 GraphQL API)
        
        inviteEnterpriseMember 创建的是 EnterpriseMemberInvitation (unaffiliated member)
        需要用 pendingUnaffiliatedMemberInvitations 查询
        
        Returns:
            字典，key 为邮箱(小写)，value 为邀请信息 {id, email, created_at}
        """
        if not self.enterprise_id:
            return {}
        
        pending = {}
        
        # 查询 pendingUnaffiliatedMemberInvitations (EnterpriseMemberInvitation 类型)
        # 这是 inviteEnterpriseMember 创建的邀请类型
        query_unaffiliated = """
        query($slug: String!) {
            enterprise(slug: $slug) {
                ownerInfo {
                    pendingUnaffiliatedMemberInvitations(first: 100) {
                        edges {
                            node {
                                id
                                email
                                createdAt
                                invitee {
                                    login
                                }
                            }
                        }
                    }
                }
            }
        }
        """
        
        try:
            data = self._graphql_request(query_unaffiliated, {"slug": self.enterprise})
            
            if data and "enterprise" in data and data["enterprise"]:
                enterprise = data["enterprise"]
                owner_info = enterprise.get("ownerInfo", {})
                invitations_data = owner_info.get("pendingUnaffiliatedMemberInvitations", {})
                edges = invitations_data.get("edges", [])
                
                print(f"  [DEBUG] pendingUnaffiliatedMemberInvitations 返回 {len(edges)} 条邀请")
                
                for edge in edges:
                    node = edge.get("node", {})
                    if node and node.get("email"):
                        email = node["email"].lower()
                        pending[email] = {
                            "id": node.get("id"),
                            "email": node.get("email"),
                            "created_at": node.get("createdAt", ""),
                            "invitee": node.get("invitee", {}).get("login") if node.get("invitee") else None
                        }
        except Exception as e:
            print(f"  [DEBUG] 获取 pendingUnaffiliatedMemberInvitations 出错: {e}")
        
        # 也查询 pendingMemberInvitations (OrganizationInvitation 类型，组织级邀请)
        query_member = """
        query($slug: String!) {
            enterprise(slug: $slug) {
                ownerInfo {
                    pendingMemberInvitations(first: 100) {
                        edges {
                            node {
                                id
                                email
                                createdAt
                            }
                        }
                    }
                }
            }
        }
        """
        
        try:
            data = self._graphql_request(query_member, {"slug": self.enterprise})
            
            if data and "enterprise" in data and data["enterprise"]:
                enterprise = data["enterprise"]
                owner_info = enterprise.get("ownerInfo", {})
                invitations_data = owner_info.get("pendingMemberInvitations", {})
                edges = invitations_data.get("edges", [])
                
                print(f"  [DEBUG] pendingMemberInvitations 返回 {len(edges)} 条邀请")
                
                for edge in edges:
                    node = edge.get("node", {})
                    if node and node.get("email"):
                        email = node["email"].lower()
                        if email not in pending:  # 避免重复
                            pending[email] = {
                                "id": node.get("id"),
                                "email": node.get("email"),
                                "created_at": node.get("createdAt", ""),
                                "type": "organization_invitation"
                            }
        except Exception as e:
            print(f"  [DEBUG] 获取 pendingMemberInvitations 出错: {e}")
        
        return pending
    
    def cancel_enterprise_invitation(self, invitation_id: str, invitation_type: str = None) -> Tuple[bool, str]:
        """
        撤销 Enterprise 邀请 (使用 GraphQL API)
        
        Args:
            invitation_id: 邀请的 Node ID
            invitation_type: 邀请类型，用于判断使用哪个 mutation
            
        Returns:
            (成功标志, 消息)
        """
        if not invitation_id:
            return False, "邀请 ID 为空"
        
        # 优先尝试 cancelEnterpriseMemberInvitation (用于 unaffiliated member 邀请)
        # 这是 inviteEnterpriseMember 创建的邀请类型
        mutation_member = """
        mutation($invitationId: ID!) {
            cancelEnterpriseMemberInvitation(input: {invitationId: $invitationId}) {
                invitation {
                    id
                }
                message
            }
        }
        """
        
        try:
            variables = {"invitationId": invitation_id}
            data = self._graphql_request(mutation_member, variables)
            return True, "已撤销邀请 (EnterpriseMemberInvitation)"
        except Exception as e:
            print(f"  [DEBUG] cancelEnterpriseMemberInvitation 失败: {e}")
            
            # 如果失败，尝试 cancelEnterpriseAdminInvitation (用于 admin 邀请)
            mutation_admin = """
            mutation($invitationId: ID!) {
                cancelEnterpriseAdminInvitation(input: {invitationId: $invitationId}) {
                    invitation {
                        id
                    }
                    message
                }
            }
            """
            try:
                variables = {"invitationId": invitation_id}
                data = self._graphql_request(mutation_admin, variables)
                return True, "已撤销邀请 (EnterpriseAdminInvitation)"
            except Exception as e2:
                return False, f"撤销邀请失败: member={str(e)}, admin={str(e2)}"
    
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
    
    def remove_from_enterprise(self, username: str) -> Tuple[bool, str]:
        """
        从 Enterprise 移除成员 (使用 GraphQL API)
        
        Args:
            username: 用户名
            
        Returns:
            (成功标志, 消息)
        """
        if not self.enterprise_id:
            return False, "无法移除: Enterprise ID 未获取"
        
        # 首先获取用户的 ID
        user_query = """
        query($login: String!) {
            user(login: $login) {
                id
            }
        }
        """
        
        try:
            user_data = self._graphql_request(user_query, {"login": username})
            if not user_data or "user" not in user_data or not user_data["user"]:
                return False, f"找不到用户 {username}"
            
            user_id = user_data["user"]["id"]
            
            # 使用 GraphQL mutation 移除成员
            mutation = """
            mutation($enterpriseId: ID!, $userId: ID!) {
                removeEnterpriseMember(input: {enterpriseId: $enterpriseId, userId: $userId}) {
                    clientMutationId
                }
            }
            """
            
            variables = {
                "enterpriseId": self.enterprise_id,
                "userId": user_id
            }
            self._graphql_request(mutation, variables)
            return True, "已从 Enterprise 移除"
        except Exception as e:
            return False, f"移除失败: {str(e)}"
    
    def invite_to_enterprise(self, email: str, retry_count: int = 0) -> Tuple[bool, str]:
        """
        邀请用户加入 Enterprise (使用 GraphQL API)
        如果已有待处理邀请，先删除再重新发送
        
        Args:
            email: 用户邮箱
            retry_count: 当前重试次数（用于防止无限递归）
            
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
            
            if data and "inviteEnterpriseMember" in data and data["inviteEnterpriseMember"]:
                result = data["inviteEnterpriseMember"]
                if result.get("invitation"):
                    invitation = result.get("invitation")
                    return True, f"已发送邀请 (ID: {invitation['id']})"
            
            # 检查错误信息
            error_str = str(data) if data else ""
            
            # 如果还未重试，尝试删除所有待处理邀请然后重新发送
            if retry_count == 0:
                print(f"     🔄 发送邀请失败或响应异常，尝试清理旧邀请...")
                try:
                    pending = self.get_pending_invitations()
                    if pending and email.lower() in pending:
                        old_inv = pending[email.lower()]
                        print(f"     🗑️  找到旧邀请 (ID: {old_inv['id']}，创建于: {old_inv['created_at']})，正在删除...")
                        cancel_success, cancel_msg = self.cancel_enterprise_invitation(old_inv["id"])
                        if cancel_success:
                            print(f"     ✅ 旧邀请已删除，重新发送...")
                            return self.invite_to_enterprise(email, retry_count=1)
                except Exception as cleanup_e:
                    print(f"     ⚠️  清理过程出错: {cleanup_e}")
            
            # 输出完整的响应以调试
            import json
            print(f"  [DEBUG] 邀请响应: {json.dumps(data, ensure_ascii=False, indent=2)}")
            return False, f"响应异常: {error_str[:100]}"
        except Exception as e:
            error_msg = str(e)
            
            # 如果还未重试，尝试删除旧邀请
            if retry_count == 0 and ("duplicate" in error_msg.lower() or "already" in error_msg.lower()):
                print(f"     🔄 检测到邀请已存在，正在清理旧邀请...")
                try:
                    pending = self.get_pending_invitations()
                    if pending and email.lower() in pending:
                        old_inv = pending[email.lower()]
                        print(f"     🗑️  找到旧邀请 (ID: {old_inv['id']})，正在删除...")
                        cancel_success, cancel_msg = self.cancel_enterprise_invitation(old_inv["id"])
                        if cancel_success:
                            print(f"     ✅ 旧邀请已删除，重新发送...")
                            return self.invite_to_enterprise(email, retry_count=1)
                    else:
                        # 没找到待处理邀请，直接重试（可能 API 缓存延迟）
                        print(f"     ⏳ 等待 API 更新后重试...")
                        import time
                        time.sleep(1)
                        return self.invite_to_enterprise(email, retry_count=1)
                except Exception as cleanup_e:
                    print(f"     ⚠️  清理过程出错: {cleanup_e}")
            
            return False, f"邀请失败: {error_msg[:100]}"
    
    def is_email(self, identifier: str) -> bool:
        """判断是否为邮箱地址"""
        return "@" in identifier
    
    # ==================== Enterprise Team 管理 ====================
    
    def create_enterprise_team(self, team_name: str) -> Tuple[bool, Dict]:
        """
        创建 Enterprise Team
        
        Args:
            team_name: Team 名称
            
        Returns:
            (成功标志, team 信息字典或错误信息)
        """
        url = f"{self.base_url}/enterprises/{self.enterprise}/teams"
        
        try:
            success, data = self._make_request(
                "POST",
                url,
                json={"name": team_name}
            )
            
            if success:
                return True, {"id": data.get("id"), "slug": data.get("slug"), "name": data.get("name")}
            else:
                return False, f"创建 Team 失败: {data}"
        except Exception as e:
            return False, f"创建 Team 失败: {str(e)}"
    
    def get_or_create_team(self, team_name: str) -> Tuple[bool, Dict]:
        """
        获取或创建 Enterprise Team
        
        Args:
            team_name: Team 名称
            
        Returns:
            (成功标志, team 信息字典或错误信息)
        """
        # 先尝试查找
        success, result = self.get_team_by_name(team_name)
        if success:
            return True, result
        
        # 不存在则创建
        print(f"  📝 Team '{team_name}' 不存在，正在创建...")
        return self.create_enterprise_team(team_name)
    
    # ==================== Organization 管理 ====================
    
    def get_enterprise_organizations(self) -> Tuple[bool, Dict[str, Dict]]:
        """
        获取 Enterprise 下的所有 Organizations (使用 GraphQL API)
        
        Returns:
            (成功标志, organizations 字典 {login_lower: {id, login, name}})
        """
        if not self.enterprise_id:
            return False, {}
        
        query = """
        query($slug: String!, $cursor: String) {
            enterprise(slug: $slug) {
                organizations(first: 100, after: $cursor) {
                    pageInfo {
                        hasNextPage
                        endCursor
                    }
                    nodes {
                        id
                        login
                        name
                    }
                }
            }
        }
        """
        
        orgs = {}
        cursor = None
        
        try:
            while True:
                variables = {"slug": self.enterprise}
                if cursor:
                    variables["cursor"] = cursor
                
                data = self._graphql_request(query, variables)
                
                if not data or "enterprise" not in data or not data["enterprise"]:
                    break
                
                orgs_data = data["enterprise"].get("organizations", {})
                nodes = orgs_data.get("nodes", [])
                
                for org in nodes:
                    if org and org.get("login"):
                        orgs[org["login"].lower()] = {
                            "id": org.get("id"),
                            "login": org.get("login"),
                            "name": org.get("name")
                        }
                
                page_info = orgs_data.get("pageInfo", {})
                if not page_info.get("hasNextPage"):
                    break
                
                cursor = page_info.get("endCursor")
            
            return True, orgs
        except Exception as e:
            print(f"  ⚠️  获取 Organizations 失败: {e}")
            return False, {}
    
    def create_organization(self, org_login: str, admin_login: str, billing_email: str = None) -> Tuple[bool, str]:
        """
        在 Enterprise 下创建 Organization (使用 GraphQL API)
        
        Args:
            org_login: Organization 登录名 (slug)
            admin_login: 管理员用户名
            billing_email: 账单邮箱 (必须)
            
        Returns:
            (成功标志, 消息)
        """
        if not self.enterprise_id:
            return False, "无法创建: Enterprise ID 未获取"
        
        if not billing_email:
            return False, "无法创建: 需要提供 billing_email"
        
        mutation = """
        mutation($enterpriseId: ID!, $login: String!, $profileName: String!, $adminLogins: [String!]!, $billingEmail: String!) {
            createEnterpriseOrganization(input: {
                enterpriseId: $enterpriseId,
                login: $login,
                profileName: $profileName,
                adminLogins: $adminLogins,
                billingEmail: $billingEmail
            }) {
                organization {
                    id
                    login
                    name
                }
            }
        }
        """
        
        try:
            variables = {
                "enterpriseId": self.enterprise_id,
                "login": org_login,
                "profileName": org_login,
                "adminLogins": [admin_login],
                "billingEmail": billing_email
            }
            data = self._graphql_request(mutation, variables)
            
            if data and "createEnterpriseOrganization" in data:
                org = data["createEnterpriseOrganization"]["organization"]
                return True, f"已创建 Organization: {org['login']}"
            else:
                return False, "响应格式不正确"
        except Exception as e:
            return False, f"创建失败: {str(e)}"
    
    def get_or_create_organization(self, org_login: str, admin_login: str, billing_email: str = None) -> Tuple[bool, Dict]:
        """
        获取或创建 Organization
        
        Args:
            org_login: Organization 登录名
            admin_login: 管理员用户名 (创建时使用)
            billing_email: 账单邮箱 (创建时使用)
            
        Returns:
            (成功标志, org 信息或错误消息)
        """
        # 先获取所有 orgs
        success, orgs = self.get_enterprise_organizations()
        
        if success and org_login.lower() in orgs:
            return True, orgs[org_login.lower()]
        
        # 不存在则创建
        print(f"  📝 Organization '{org_login}' 不存在，正在创建...")
        success, message = self.create_organization(org_login, admin_login, billing_email)
        if success:
            # 重新获取以得到完整信息
            success, orgs = self.get_enterprise_organizations()
            if success and org_login.lower() in orgs:
                return True, orgs[org_login.lower()]
            return True, {"login": org_login}
        return False, message
    
    def get_organization_members(self, org_login: str) -> Tuple[bool, Set[str]]:
        """
        获取 Organization 的所有成员
        
        Args:
            org_login: Organization 登录名
            
        Returns:
            (成功标志, 成员用户名集合)
        """
        url = f"{self.base_url}/orgs/{org_login}/members"
        members = set()
        page = 1
        
        try:
            while True:
                success, data = self._make_request(
                    "GET",
                    f"{url}?per_page=100&page={page}"
                )
                
                if not success:
                    return False, set()
                
                if not data:
                    break
                
                for member in data:
                    members.add(member["login"])
                
                if len(data) < 100:
                    break
                page += 1
            
            return True, members
        except Exception as e:
            print(f"  ⚠️  获取 Organization 成员失败: {e}")
            return False, set()
    
    def get_organization_pending_invitations(self, org_login: str) -> Dict[str, Dict]:
        """
        获取 Organization 的待处理邀请
        
        Args:
            org_login: Organization 登录名
            
        Returns:
            字典，key 为邮箱(小写)或用户名(小写)，value 为邀请信息
        """
        url = f"{self.base_url}/orgs/{org_login}/invitations"
        pending = {}
        page = 1
        
        try:
            while True:
                success, data = self._make_request(
                    "GET",
                    f"{url}?per_page=100&page={page}"
                )
                
                if not success or not data:
                    break
                
                for inv in data:
                    key = (inv.get("email") or inv.get("login", "")).lower()
                    if key:
                        pending[key] = {
                            "id": inv.get("id"),
                            "email": inv.get("email"),
                            "login": inv.get("login"),
                            "role": inv.get("role"),
                            "created_at": inv.get("created_at", "")
                        }
                
                if len(data) < 100:
                    break
                page += 1
            
            return pending
        except Exception as e:
            print(f"  ⚠️  获取 Organization 待处理邀请失败: {e}")
            return {}
    
    def cancel_organization_invitation(self, org_login: str, invitation_id: int) -> Tuple[bool, str]:
        """
        撤销 Organization 邀请
        
        Args:
            org_login: Organization 登录名
            invitation_id: 邀请 ID
            
        Returns:
            (成功标志, 消息)
        """
        url = f"{self.base_url}/orgs/{org_login}/invitations/{invitation_id}"
        
        try:
            success, data = self._make_request("DELETE", url)
            if success:
                return True, "已撤销邀请"
            else:
                return False, f"撤销失败: {data}"
        except Exception as e:
            return False, f"撤销失败: {str(e)}"
    
    def add_member_to_organization(self, org_login: str, username: str = None, email: str = None, role: str = "member") -> Tuple[bool, str]:
        """
        添加成员到 Organization (通过邀请)
        
        Args:
            org_login: Organization 登录名
            username: 用户名 (可选)
            email: 邮箱 (可选，username 和 email 至少提供一个)
            role: 角色 (admin 或 member)
            
        Returns:
            (成功标志, 消息)
        """
        url = f"{self.base_url}/orgs/{org_login}/invitations"
        
        payload = {"role": role}
        if email:
            payload["email"] = email
        elif username:
            # 需要先获取用户 ID
            user_url = f"{self.base_url}/users/{username}"
            success, user_data = self._make_request("GET", user_url)
            if success and user_data.get("id"):
                payload["invitee_id"] = user_data["id"]
            else:
                return False, f"找不到用户 {username}"
        else:
            return False, "需要提供 username 或 email"
        
        try:
            success, data = self._make_request("POST", url, json=payload)
            if success:
                return True, "已发送邀请"
            else:
                return False, f"邀请失败: {data}"
        except Exception as e:
            return False, f"邀请失败: {str(e)}"
    
    def remove_member_from_organization(self, org_login: str, username: str) -> Tuple[bool, str]:
        """
        从 Organization 移除成员
        
        Args:
            org_login: Organization 登录名
            username: 用户名
            
        Returns:
            (成功标志, 消息)
        """
        url = f"{self.base_url}/orgs/{org_login}/members/{username}"
        
        try:
            success, data = self._make_request("DELETE", url)
            if success:
                return True, "已从 Organization 移除"
            else:
                return False, f"移除失败: {data}"
        except Exception as e:
            return False, f"移除失败: {str(e)}"
    
    def sync_organization(self, org_config: Dict) -> Dict:
        """
        同步单个 Organization 的成员
        
        Args:
            org_config: Organization 配置 {login, admin, billing_email, members: [...]}
            
        Returns:
            同步报告
        """
        org_login = org_config.get("login")
        admin_login = org_config.get("admin", "")
        billing_email = org_config.get("billing_email", "")
        target_members = org_config.get("members", [])
        
        print(f"\n{'='*60}")
        print(f"正在同步 Organization: {org_login}")
        print(f"{'='*60}")
        
        org_report = {
            "login": org_login,
            "added": [],
            "removed": [],
            "invited": [],
            "errors": []
        }
        
        # 1. 确保 Organization 存在
        print(f"\n📋 检查 Organization...")
        success, result = self.get_or_create_organization(org_login, admin_login, billing_email)
        if not success:
            error_msg = f"无法获取/创建 Organization: {result}"
            print(f"  ❌ {error_msg}")
            org_report["errors"].append(error_msg)
            return org_report
        print(f"  ✅ Organization 已就绪: {org_login}")
        
        # 2. 获取当前 Organization 成员
        print(f"\n📋 获取当前 Organization 成员...")
        success, current_members = self.get_organization_members(org_login)
        if not success:
            error_msg = "无法获取 Organization 成员列表"
            print(f"  ❌ {error_msg}")
            org_report["errors"].append(error_msg)
            return org_report
        
        print(f"  ✅ 当前成员数: {len(current_members)}")
        
        # 3. 获取待处理邀请
        print(f"\n📋 获取待处理邀请...")
        pending_invitations = self.get_organization_pending_invitations(org_login)
        if pending_invitations:
            print(f"  ✅ 待处理邀请数: {len(pending_invitations)}")
        else:
            print(f"  ℹ️  无待处理邀请")
        
        # 4. 处理目标成员
        current_identifiers = {m.lower(): m for m in current_members}
        
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
        
        print(f"\n🔍 差异分析:")
        print(f"  • 当前成员: {len(current_keys)}")
        print(f"  • 目标成员: {len(target_keys)}")
        print(f"  • 需要添加: {len(to_add)}")
        print(f"  • 需要移除: {len(to_remove)}")
        
        # 5. 添加成员
        if to_add:
            print(f"\n➕ 添加成员到 Organization...")
            for key in to_add:
                info = target_identifiers[key]
                username = info['username']
                email = info['email']
                
                # 检查是否已有待处理邀请
                if email and email.lower() in pending_invitations:
                    # 先撤销旧邀请
                    old_inv = pending_invitations[email.lower()]
                    print(f"  🔄 {email}: 已有待处理邀请，先撤销...")
                    self.cancel_organization_invitation(org_login, old_inv["id"])
                elif key in pending_invitations:
                    old_inv = pending_invitations[key]
                    print(f"  🔄 {username}: 已有待处理邀请，先撤销...")
                    self.cancel_organization_invitation(org_login, old_inv["id"])
                
                # 发送邀请
                success, message = self.add_member_to_organization(org_login, username=username, email=email)
                if success:
                    print(f"  ✅ {username}: {message}")
                    org_report["invited"].append(username)
                else:
                    print(f"  ❌ {username}: {message}")
                    org_report["errors"].append(f"{username}: {message}")
        
        # 6. 移除成员
        if to_remove:
            print(f"\n➖ 从 Organization 移除成员...")
            for key in to_remove:
                username = current_identifiers[key]
                success, message = self.remove_member_from_organization(org_login, username)
                if success:
                    print(f"  ✅ {username}: {message}")
                    org_report["removed"].append(username)
                else:
                    print(f"  ❌ {username}: {message}")
                    org_report["errors"].append(f"{username}: {message}")
        
        return org_report
    
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
    
    def sync_team(self, team_name: str, target_members: List[str], team_id: int = None, team_slug: str = None, auto_create: bool = True) -> Dict:
        """
        同步单个 Team 的成员
        
        Args:
            team_name: Team 名称
            target_members: 目标成员列表
            team_id: Team 的 ID (可选，如果不提供会自动查找)
            team_slug: Team 的 slug (可选，用于显示)
            auto_create: 是否自动创建不存在的 Team
            
        Returns:
            同步报告
        """
        # 如果没有提供 ID，尝试通过名称查找或创建
        if not team_id:
            print(f"\n🔍 正在查找 Team: {team_name}...")
            success, result = self.get_team_by_name(team_name)
            if not success:
                if auto_create:
                    print(f"  📝 Team 不存在，正在创建...")
                    success, result = self.create_enterprise_team(team_name)
                    if not success:
                        print(f"  ❌ 创建 Team 失败: {result}")
                        return {
                            "name": team_name,
                            "slug": None,
                            "added": [],
                            "removed": [],
                            "invited": [],
                            "errors": [f"创建 Team 失败: {result}"]
                        }
                    print(f"  ✅ 已创建 Team (ID: {result['id']}, slug: {result['slug']})")
                else:
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
            if success and not auto_create:
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
        print(f"\n📋 获取待处理邀请...")
        pending_invitations = self.get_pending_invitations()
        
        if pending_invitations:
            print(f"  ✅ 待处理邀请数: {len(pending_invitations)}")
            for email, info in pending_invitations.items():
                print(f"     📧 {email} (邀请 ID: {info['id']}, 创建时间: {info['created_at'][:10] if info.get('created_at') else 'N/A'})")
        else:
            print(f"  ℹ️  无待处理邀请 (可能是 API 缓存延迟或邀请已接受)")
        
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
                
                # 先检查用户是否已经在 Enterprise 中
                username_in_enterprise = username.lower() in {m.lower() for m in enterprise_members}
                
                if username_in_enterprise:
                    # 用户已在 Enterprise 中，直接添加到 Team
                    success, message = self.add_member_to_team(team_id, username)
                    if success:
                        print(f"  ✅ {username}: {message}")
                        team_report["added"].append(username)
                    else:
                        print(f"  ❌ {username}: {message}")
                        team_report["errors"].append(f"{username}: {message}")
                elif email:
                    # 用户不在 Enterprise 中，需要发送邀请
                    email_lower = email.lower()
                    # 如果已有待处理邀请，先删除旧邀请
                    if email_lower in pending_invitations:
                        old_invitation = pending_invitations[email_lower]
                        print(f"  🔄 {email}: 已有待处理邀请，先撤销旧邀请...")
                        cancel_success, cancel_msg = self.cancel_enterprise_invitation(old_invitation["id"])
                        if cancel_success:
                            print(f"     ✅ {cancel_msg}")
                        else:
                            print(f"     ⚠️ {cancel_msg}")
                    
                    # 发送新邀请
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
                            # 没有 email，无法邀请
                            print(f"  ⚠️ {username}: 用户不在 Enterprise 中，且没有提供 email 无法发送邀请")
                            team_report["errors"].append(f"{username}: 用户不在 Enterprise 中，需要提供 email 才能发送邀请")
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
        从配置文件同步所有 Teams 和 Organizations
        
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
        orgs = config.get("orgs", [])
        
        print(f"\n🚀 开始同步 Enterprise: {self.enterprise}")
        if teams:
            print(f"📝 共需处理 {len(teams)} 个 Enterprise Team(s)")
        if orgs:
            print(f"📝 共需处理 {len(orgs)} 个 Organization(s)")
        
        # 收集所有 config 中的用户名 (用于后续清理 Enterprise)
        all_config_usernames = set()
        
        # 初始化报告中的 orgs 列表
        if "orgs" not in self.report:
            self.report["orgs"] = []
        
        # 同步每个 Organization
        for org in orgs:
            org_login = org.get("login")
            members = org.get("members", [])
            
            if not org_login:
                print("⚠️  跳过没有 login 的 organization")
                continue
            
            # 收集该 org 的用户名
            for member in members:
                if isinstance(member, dict):
                    username = member.get('username', '').strip()
                    if username:
                        all_config_usernames.add(username.lower())
                elif isinstance(member, str) and not self.is_email(member):
                    all_config_usernames.add(member.lower())
            
            org_report = self.sync_organization(org)
            self.report["orgs"].append(org_report)
        
        # 同步每个 Team
        for team in teams:
            team_name = team.get("name")
            members = team.get("members", [])
            team_id = team.get("id")  # 可选的 team ID
            team_slug = team.get("slug")  # 可选的 slug
            
            if not team_name:
                print("⚠️  跳过没有名称的 team")
                continue
            
            # 收集该 team 的用户名
            for member in members:
                if isinstance(member, dict):
                    username = member.get('username', '').strip()
                    if username:
                        all_config_usernames.add(username.lower())
                elif isinstance(member, str) and not self.is_email(member):
                    all_config_usernames.add(member.lower())
            
            team_report = self.sync_team(team_name, members, team_id, team_slug)
            self.report["teams"].append(team_report)
        
        # 清理 Enterprise 成员：移除不在 reserved_members 和 teams 配置中的成员
        self.cleanup_enterprise_members(config, all_config_usernames)
        
        # 生成报告
        self.generate_report()
    
    def cleanup_enterprise_members(self, config: Dict, all_config_usernames: Set[str]):
        """
        清理 Enterprise 成员：移除不在 reserved_members 和 teams 配置中的成员
        
        Args:
            config: 配置字典
            all_config_usernames: 所有 team 配置中的用户名集合 (小写)
        """
        reserved_members = config.get("reserved_members", [])
        
        # 将 reserved_members 转换为小写集合
        reserved_set = set()
        for member in reserved_members:
            if isinstance(member, str):
                reserved_set.add(member.lower())
            elif isinstance(member, dict):
                username = member.get('username', '').strip()
                if username:
                    reserved_set.add(username.lower())
        
        # 合并：保留的用户 = reserved_members + 所有 team 中的用户
        protected_users = reserved_set | all_config_usernames
        
        print(f"\n{'='*60}")
        print("🧹 清理 Enterprise 成员")
        print(f"{'='*60}")
        print(f"  • 保留成员 (reserved_members): {len(reserved_set)}")
        if reserved_set:
            for u in sorted(reserved_set):
                print(f"    - {u}")
        print(f"  • Teams 配置中的成员: {len(all_config_usernames)}")
        
        # 获取当前 Enterprise 成员
        success, enterprise_members = self.get_enterprise_members()
        if not success:
            print(f"  ⚠️  无法获取 Enterprise 成员列表，跳过清理")
            return
        
        print(f"  • 当前 Enterprise 成员: {len(enterprise_members)}")
        
        # 找出需要移除的成员
        to_remove_from_enterprise = set()
        for member in enterprise_members:
            if member.lower() not in protected_users:
                to_remove_from_enterprise.add(member)
        
        if not to_remove_from_enterprise:
            print(f"\n  ✅ 无需移除任何成员")
            return
        
        print(f"\n  🗑️  需要从 Enterprise 移除: {len(to_remove_from_enterprise)} 人")
        for username in sorted(to_remove_from_enterprise):
            print(f"    - {username}")
        
        # 初始化报告中的 enterprise_removed
        if "enterprise_removed" not in self.report:
            self.report["enterprise_removed"] = []
        if "enterprise_remove_errors" not in self.report:
            self.report["enterprise_remove_errors"] = []
        
        # 执行移除
        print(f"\n  ➖ 从 Enterprise 移除成员...")
        for username in to_remove_from_enterprise:
            success, message = self.remove_from_enterprise(username)
            if success:
                print(f"    ✅ {username}: {message}")
                self.report["enterprise_removed"].append(username)
            else:
                print(f"    ❌ {username}: {message}")
                self.report["enterprise_remove_errors"].append(f"{username}: {message}")
    
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
        
        # Organization 报告
        for org_report in self.report.get("orgs", []):
            org_login = org_report.get("login", "unknown")
            print(f"Organization: {org_login}")
            report_lines.append(f"Organization: {org_login}")
            report_lines.append("-" * 60)
            
            if org_report.get("added"):
                print(f"\n  ✅ 成功添加 ({len(org_report['added'])} 人):")
                report_lines.append(f"\n✅ 成功添加 ({len(org_report['added'])} 人):")
                for member in org_report["added"]:
                    print(f"     • {member}")
                    report_lines.append(f"  • {member}")
            
            if org_report.get("invited"):
                print(f"\n  📧 已发送邀请 ({len(org_report['invited'])} 人):")
                report_lines.append(f"\n📧 已发送邀请 ({len(org_report['invited'])} 人):")
                for member in org_report["invited"]:
                    print(f"     • {member}")
                    report_lines.append(f"  • {member}")
            
            if org_report.get("removed"):
                print(f"\n  ➖ 已移除 ({len(org_report['removed'])} 人):")
                report_lines.append(f"\n➖ 已移除 ({len(org_report['removed'])} 人):")
                for member in org_report["removed"]:
                    print(f"     • {member}")
                    report_lines.append(f"  • {member}")
            
            if org_report.get("errors"):
                print(f"\n  ❌ 错误 ({len(org_report['errors'])} 个):")
                report_lines.append(f"\n❌ 错误 ({len(org_report['errors'])} 个):")
                for error in org_report["errors"]:
                    print(f"     • {error}")
                    report_lines.append(f"  • {error}")
            
            print("")
            report_lines.append("")
            report_lines.append("")
        
        # Team 报告
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
        
        # Enterprise 成员移除报告
        enterprise_removed = self.report.get("enterprise_removed", [])
        enterprise_remove_errors = self.report.get("enterprise_remove_errors", [])
        
        if enterprise_removed or enterprise_remove_errors:
            print(f"{'='*60}")
            print("Enterprise 成员清理")
            print(f"{'='*60}")
            report_lines.append("=" * 60)
            report_lines.append("Enterprise 成员清理")
            report_lines.append("-" * 60)
            
            if enterprise_removed:
                print(f"\n  🗑️  从 Enterprise 移除 ({len(enterprise_removed)} 人):")
                report_lines.append(f"\n🗑️ 从 Enterprise 移除 ({len(enterprise_removed)} 人):")
                for member in enterprise_removed:
                    print(f"     • {member}")
                    report_lines.append(f"  • {member}")
            
            if enterprise_remove_errors:
                print(f"\n  ❌ 移除失败 ({len(enterprise_remove_errors)} 个):")
                report_lines.append(f"\n❌ 移除失败 ({len(enterprise_remove_errors)} 个):")
                for error in enterprise_remove_errors:
                    print(f"     • {error}")
                    report_lines.append(f"  • {error}")
            
            print("")
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
