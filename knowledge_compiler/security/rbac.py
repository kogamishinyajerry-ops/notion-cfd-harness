#!/usr/bin/env python3
"""
P5-07: RBAC - Role-Based Access Control

Provides:
- Role definitions
- Permission system
- Policy evaluation
- Access control checking
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Set, Optional, Callable


# ============================================================================
# Actions and Resources
# ============================================================================

class Action(Enum):
    """Standard actions for permissions"""
    READ = "read"
    WRITE = "write"
    DELETE = "delete"
    EXECUTE = "execute"
    ADMIN = "admin"


# ============================================================================
# Permission
# ============================================================================

@dataclass(frozen=True)
class Permission:
    """
    A permission grants access to a specific action on a resource

    Format: resource:action (e.g., "memory_network:read")
    """

    resource: str
    action: str

    def __str__(self) -> str:
        return f"{self.resource}:{self.action}"

    @classmethod
    def parse(cls, permission_str: str) -> "Permission":
        """
        Parse permission string

        Args:
            permission_str: Permission in format "resource:action"

        Returns:
            Permission instance
        """
        parts = permission_str.split(":", 1)
        if len(parts) != 2:
            raise ValueError(f"Invalid permission format: {permission_str}")
        return cls(resource=parts[0], action=parts[1])

    def matches(self, resource_pattern: str, action_pattern: str) -> bool:
        """
        Check if permission matches patterns

        Supports wildcard (*) in both permission and patterns

        Args:
            resource_pattern: Resource pattern to check (e.g., "memory_network", "*")
            action_pattern: Action pattern to check (e.g., "read", "*")

        Returns:
            True if permission matches or grants the pattern
        """
        # Check resource match
        # 1. Exact match
        if self.resource == resource_pattern:
            resource_matches = True
        # 2. Permission is wildcard (*)
        elif self.resource == "*":
            resource_matches = True
        # 3. Pattern is wildcard (*)
        elif resource_pattern == "*":
            resource_matches = True
        # 4. Prefix wildcard (permission "mem_*" matches "memory_network")
        elif self.resource.endswith("*") and resource_pattern.startswith(self.resource[:-1]):
            resource_matches = True
        # 5. Prefix wildcard (pattern "mem_*" matches permission "memory_network")
        elif resource_pattern.endswith("*") and self.resource.startswith(resource_pattern[:-1]):
            resource_matches = True
        else:
            resource_matches = False

        # Check action match (same logic)
        if self.action == action_pattern:
            action_matches = True
        elif self.action == "*":
            action_matches = True
        elif action_pattern == "*":
            action_matches = True
        elif self.action.endswith("*") and action_pattern.startswith(self.action[:-1]):
            action_matches = True
        elif action_pattern.endswith("*") and self.action.startswith(action_pattern[:-1]):
            action_matches = True
        else:
            action_matches = False

        return resource_matches and action_matches


# ============================================================================
# Role
# ============================================================================

@dataclass
class Role:
    """
    A role represents a collection of permissions

    Attributes:
        name: Role name
        permissions: Set of permissions granted by this role
        description: Human-readable description
    """

    name: str
    permissions: Set[Permission] = field(default_factory=set)
    description: str = ""

    def __hash__(self) -> int:
        """Hash based on name (for use in sets)"""
        return hash(self.name)

    def __eq__(self, other: object) -> bool:
        """Equality based on name"""
        if not isinstance(other, Role):
            return False
        return self.name == other.name

    def add_permission(self, permission: Permission) -> None:
        """Add a permission to this role"""
        self.permissions.add(permission)

    def remove_permission(self, permission: Permission) -> None:
        """Remove a permission from this role"""
        self.permissions.discard(permission)

    def has_permission(self, permission: Permission) -> bool:
        """Check if role grants a permission"""
        return permission in self.permissions

    def can(
        self,
        resource: str,
        action: str,
    ) -> bool:
        """Check if role can perform action on resource"""
        # Check if any permission grants access
        for perm in self.permissions:
            if perm.matches(resource, action):
                return True
        return False


# ============================================================================
# Predefined Roles
# ============================================================================

class Roles:
    """Predefined roles for the system"""

    @staticmethod
    def admin() -> Role:
        """Administrator with all permissions"""
        return Role(
            name="admin",
            permissions={Permission("*", "*")},
            description="Full system access",
        )

    @staticmethod
    def reader() -> Role:
        """Read-only access"""
        return Role(
            name="reader",
            permissions={
                Permission("memory_network", "read"),
                Permission("cache", "read"),
                Permission("index", "read"),
            },
            description="Read-only access",
        )

    @staticmethod
    def writer() -> Role:
        """Read and write access"""
        role = Roles.reader()
        role.name = "writer"
        role.permissions.update({
            Permission("memory_network", "write"),
            Permission("cache", "write"),
            Permission("index", "write"),
        })
        role.description = "Read and write access"
        return role

    @staticmethod
    def operator() -> Role:
        """Operational access (can execute operations)"""
        return Role(
            name="operator",
            permissions={
                Permission("memory_network", "read"),
                Permission("memory_network", "execute"),
                Permission("metrics", "read"),
                Permission("health", "read"),
            },
            description="Operational access",
        )


# ============================================================================
# User
# ============================================================================

@dataclass
class User:
    """
    A user with roles and direct permissions

    Attributes:
        user_id: Unique user identifier
        roles: Set of roles assigned to user
        permissions: Direct permissions assigned to user
    """

    user_id: str
    roles: Set[Role] = field(default_factory=set)
    permissions: Set[Permission] = field(default_factory=set)

    def add_role(self, role: Role) -> None:
        """Add a role to the user"""
        self.roles.add(role)

    def remove_role(self, role: Role) -> None:
        """Remove a role from the user"""
        self.roles.discard(role)

    def add_permission(self, permission: Permission) -> None:
        """Add a direct permission to the user"""
        self.permissions.add(permission)

    def has_permission(self, permission: Permission) -> bool:
        """Check if user has a permission (via roles or direct)"""
        # Check direct permissions
        for perm in self.permissions:
            if perm.matches(permission.resource, permission.action):
                return True

        # Check role permissions
        for role in self.roles:
            for perm in role.permissions:
                if perm.matches(permission.resource, permission.action):
                    return True

        return False

    def can(self, resource: str, action: str) -> bool:
        """Check if user can perform action on resource"""
        return self.has_permission(Permission(resource, action))


# ============================================================================
# Policy
# ============================================================================

class PolicyEffect(Enum):
    """Policy effect"""
    ALLOW = "allow"
    DENY = "deny"


@dataclass
class Policy:
    """
    An access policy

    Attributes:
        name: Policy name
        effect: Allow or deny
        permissions: Set of permissions this policy applies to
        roles: Set of roles this policy applies to (empty = all roles)
        users: Set of user IDs this policy applies to (empty = all users)
        condition: Optional callable for conditional evaluation
    """

    name: str
    effect: PolicyEffect
    permissions: Set[Permission] = field(default_factory=set)
    roles: Set[str] = field(default_factory=set)
    users: Set[str] = field(default_factory=set)
    condition: Optional[Callable[[User, Permission], bool]] = None

    def applies_to(
        self,
        user: User,
        permission: Permission,
    ) -> bool:
        """
        Check if policy applies to user and permission

        Args:
            user: User to check
            permission: Permission to check

        Returns:
            True if policy applies
        """
        # Check permission match (policy permission grants access to requested permission)
        permission_match = False
        for policy_perm in self.permissions:
            if policy_perm.matches(permission.resource, permission.action):
                permission_match = True
                break

        if not permission_match:
            return False

        # Check user/role match
        if self.users and user.user_id not in self.users:
            return False

        if self.roles and not any(
            role.name in self.roles
            for role in user.roles
        ):
            return False

        # Check condition
        if self.condition and not self.condition(user, permission):
            return False

        return True


# ============================================================================
# RBAC Engine
# ============================================================================

class RBACEngine:
    """
    Role-Based Access Control engine

    Features:
    - User/role management
    - Permission checking
    - Policy evaluation
    - Thread-safe
    """

    def __init__(self):
        self._users: Dict[str, User] = {}
        self._roles: Dict[str, Role] = {}
        self._policies: List[Policy] = []
        self._lock = threading.Lock()

        # Initialize with default roles
        self._init_default_roles()

    def _init_default_roles(self) -> None:
        """Initialize default roles"""
        for role in [Roles.admin(), Roles.reader(), Roles.writer(), Roles.operator()]:
            self._roles[role.name] = role

    # User management

    def create_user(self, user_id: str) -> User:
        """Create a new user"""
        with self._lock:
            if user_id in self._users:
                return self._users[user_id]

            user = User(user_id=user_id)
            self._users[user_id] = user
            return user

    def get_user(self, user_id: str) -> Optional[User]:
        """Get a user by ID"""
        return self._users.get(user_id)

    def delete_user(self, user_id: str) -> None:
        """Delete a user"""
        with self._lock:
            self._users.pop(user_id, None)

    # Role management

    def create_role(self, name: str, description: str = "") -> Role:
        """Create a new role"""
        with self._lock:
            if name in self._roles:
                return self._roles[name]

            role = Role(name=name, description=description)
            self._roles[name] = role
            return role

    def get_role(self, name: str) -> Optional[Role]:
        """Get a role by name"""
        return self._roles.get(name)

    def delete_role(self, name: str) -> None:
        """Delete a role"""
        with self._lock:
            self._roles.pop(name, None)

    def assign_role(self, user_id: str, role_name: str) -> bool:
        """Assign a role to a user"""
        with self._lock:
            user = self._users.get(user_id)
            role = self._roles.get(role_name)

            if not user or not role:
                return False

            user.add_role(role)
            return True

    # Permission checking

    def check_permission(
        self,
        user_id: str,
        resource: str,
        action: str,
    ) -> bool:
        """
        Check if user has permission

        Args:
            user_id: User identifier
            resource: Resource to access
            action: Action to perform

        Returns:
            True if permission granted
        """
        user = self._users.get(user_id)
        if not user:
            return False

        permission = Permission(resource, action)

        # Check policies first (deny takes precedence)
        for policy in self._policies:
            if policy.applies_to(user, permission):
                if policy.effect == PolicyEffect.DENY:
                    return False
                elif policy.effect == PolicyEffect.ALLOW:
                    return True

        # Fall back to user's permissions
        return user.has_permission(permission)

    def can(
        self,
        user_id: str,
        resource: str,
        action: str,
    ) -> bool:
        """Alias for check_permission"""
        return self.check_permission(user_id, resource, action)

    # Policy management

    def add_policy(self, policy: Policy) -> None:
        """Add a policy"""
        with self._lock:
            self._policies.append(policy)

    def remove_policy(self, policy_name: str) -> None:
        """Remove a policy by name"""
        with self._lock:
            self._policies = [
                p for p in self._policies
                if p.name != policy_name
            ]

    def get_policies(self) -> List[Policy]:
        """Get all policies"""
        return list(self._policies)


# ============================================================================
# Decorator for access control
# ============================================================================

def require_permission(
    rbac: RBACEngine,
    resource: str,
    action: str,
):
    """
    Decorator to require permission for function access

    Args:
        rbac: RBAC engine
        resource: Resource required
        action: Action required

    Returns:
        Decorated function
    """

    def decorator(func):
        def wrapper(*args, **kwargs):
            # Get user_id from kwargs or args
            user_id = kwargs.get("user_id")
            if not user_id and len(args) > 0:
                user_id = args[0]

            if not user_id:
                raise PermissionError("user_id required")

            if not rbac.can(user_id, resource, action):
                raise PermissionError(
                    f"User '{user_id}' does not have permission "
                    f"'{action}' on resource '{resource}'"
                )

            return func(*args, **kwargs)

        return wrapper

    return decorator


# ============================================================================
# Global RBAC Engine
# ============================================================================

_global_rbac: Optional[RBACEngine] = None
_rbac_lock = threading.Lock()


def get_rbac() -> RBACEngine:
    """Get global RBAC engine"""
    global _global_rbac

    with _rbac_lock:
        if _global_rbac is None:
            _global_rbac = RBACEngine()

    return _global_rbac


# ============================================================================
# Export
# ============================================================================

__all__ = [
    "Action",
    "Permission",
    "Role",
    "Roles",
    "User",
    "PolicyEffect",
    "Policy",
    "RBACEngine",
    "get_rbac",
    "require_permission",
]
