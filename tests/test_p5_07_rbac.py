#!/usr/bin/env python3
"""
P5-07: RBAC tests
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from knowledge_compiler.security.rbac import (
    Action,
    Permission,
    Role,
    Roles,
    User,
    PolicyEffect,
    Policy,
    RBACEngine,
    get_rbac,
    require_permission,
)


class TestPermission:
    def test_permission_creation(self):
        """Permission should initialize"""
        perm = Permission(resource="memory_network", action="read")

        assert perm.resource == "memory_network"
        assert perm.action == "read"

    def test_permission_to_string(self):
        """Permission should format as string"""
        perm = Permission(resource="memory_network", action="read")

        assert str(perm) == "memory_network:read"

    def test_permission_parse(self):
        """Permission should parse from string"""
        perm = Permission.parse("cache:write")

        assert perm.resource == "cache"
        assert perm.action == "write"

    def test_permission_parse_invalid_format(self):
        """Permission.parse should raise on invalid format"""
        try:
            Permission.parse("invalid")
            assert False, "Should have raised ValueError"
        except ValueError:
            pass  # Expected

    def test_permission_matches_exact(self):
        """Permission.matches should match exact patterns"""
        perm = Permission("memory_network", "read")

        assert perm.matches("memory_network", "read") is True
        assert perm.matches("cache", "read") is False
        assert perm.matches("memory_network", "write") is False

    def test_permission_matches_wildcard_resource(self):
        """Permission.matches should match wildcard resource"""
        perm = Permission("memory_network", "read")

        assert perm.matches("*", "read") is True
        assert perm.matches("memory_*", "read") is True
        assert perm.matches("cache_*", "read") is False

    def test_permission_matches_wildcard_action(self):
        """Permission.matches should match wildcard action"""
        perm = Permission("memory_network", "read")

        assert perm.matches("memory_network", "*") is True
        assert perm.matches("memory_network", "r*") is True
        assert perm.matches("memory_network", "w*") is False

    def test_permission_matches_both_wildcards(self):
        """Permission.matches should match both wildcards"""
        perm = Permission("memory_network", "read")

        assert perm.matches("*", "*") is True


class TestRole:
    def test_role_creation(self):
        """Role should initialize"""
        role = Role(name="reader")

        assert role.name == "reader"
        assert len(role.permissions) == 0

    def test_role_with_permissions(self):
        """Role should store permissions"""
        role = Role(name="writer")
        role.add_permission(Permission("cache", "write"))
        role.add_permission(Permission("cache", "read"))

        assert len(role.permissions) == 2

    def test_role_has_permission(self):
        """Role.has_permission should check membership"""
        role = Role(name="reader")
        perm = Permission("cache", "read")
        role.add_permission(perm)

        assert role.has_permission(perm) is True
        assert role.has_permission(Permission("cache", "write")) is False

    def test_role_can(self):
        """Role.can should check resource/action access"""
        role = Role(name="reader")
        role.add_permission(Permission("cache", "read"))

        assert role.can("cache", "read") is True
        assert role.can("cache", "write") is False

    def test_role_remove_permission(self):
        """Role should allow removing permissions"""
        role = Role(name="writer")
        perm = Permission("cache", "write")
        role.add_permission(perm)

        role.remove_permission(perm)

        assert role.has_permission(perm) is False


class TestPredefinedRoles:
    def test_roles_admin(self):
        """Roles.admin should have all permissions"""
        admin = Roles.admin()

        assert admin.name == "admin"
        assert admin.can("anything", "anything") is True

    def test_roles_reader(self):
        """Roles.reader should have read permissions"""
        reader = Roles.reader()

        assert reader.name == "reader"
        assert reader.can("memory_network", "read") is True
        assert reader.can("cache", "read") is True
        assert reader.can("memory_network", "write") is False

    def test_roles_writer(self):
        """Roles.writer should have read and write permissions"""
        writer = Roles.writer()

        assert writer.name == "writer"
        assert writer.can("cache", "read") is True
        assert writer.can("cache", "write") is True
        assert writer.can("cache", "delete") is False

    def test_roles_operator(self):
        """Roles.operator should have operational permissions"""
        operator = Roles.operator()

        assert operator.name == "operator"
        assert operator.can("memory_network", "read") is True
        assert operator.can("memory_network", "execute") is True
        assert operator.can("metrics", "read") is True
        assert operator.can("cache", "write") is False


class TestUser:
    def test_user_creation(self):
        """User should initialize"""
        user = User(user_id="user123")

        assert user.user_id == "user123"
        assert len(user.roles) == 0
        assert len(user.permissions) == 0

    def test_user_with_roles(self):
        """User should store roles"""
        user = User(user_id="user123")
        role = Role(name="reader")
        user.add_role(role)

        assert role in user.roles

    def test_user_with_direct_permissions(self):
        """User should store direct permissions"""
        user = User(user_id="user123")
        perm = Permission("special", "action")
        user.add_permission(perm)

        assert perm in user.permissions

    def test_user_has_permission_via_role(self):
        """User should have permissions from roles"""
        user = User(user_id="user123")
        role = Roles.reader()
        user.add_role(role)

        assert user.has_permission(Permission("cache", "read")) is True

    def test_user_has_permission_direct(self):
        """User should have direct permissions"""
        user = User(user_id="user123")
        perm = Permission("special", "action")
        user.add_permission(perm)

        assert user.has_permission(perm) is True

    def test_user_can(self):
        """User.can should check resource/action access"""
        user = User(user_id="user123")
        user.add_role(Roles.reader())

        assert user.can("cache", "read") is True
        assert user.can("cache", "write") is False


class TestPolicy:
    def test_policy_creation(self):
        """Policy should initialize"""
        policy = Policy(
            name="allow_readers",
            effect=PolicyEffect.ALLOW,
            permissions={Permission("*", "read")},
        )

        assert policy.name == "allow_readers"
        assert policy.effect == PolicyEffect.ALLOW

    def test_policy_applies_to_permission(self):
        """Policy should check permission match"""
        policy = Policy(
            name="test",
            effect=PolicyEffect.ALLOW,
            permissions={Permission("cache", "read")},
        )

        user = User(user_id="user1")
        perm = Permission("cache", "read")

        assert policy.applies_to(user, perm) is True

        perm2 = Permission("cache", "write")
        assert policy.applies_to(user, perm2) is False

    def test_policy_applies_to_user(self):
        """Policy should check user match"""
        policy = Policy(
            name="test",
            effect=PolicyEffect.ALLOW,
            permissions={Permission("*", "*")},
            users={"user1"},
        )

        user1 = User(user_id="user1")
        perm = Permission("anything", "anything")

        assert policy.applies_to(user1, perm) is True

        user2 = User(user_id="user2")
        assert policy.applies_to(user2, perm) is False

    def test_policy_applies_to_role(self):
        """Policy should check role match"""
        policy = Policy(
            name="test",
            effect=PolicyEffect.ALLOW,
            permissions={Permission("*", "*")},
            roles={"admin"},
        )

        admin = User(user_id="admin1")
        admin.add_role(Roles.admin())

        perm = Permission("anything", "anything")

        assert policy.applies_to(admin, perm) is True

        reader = User(user_id="reader1")
        reader.add_role(Roles.reader())

        assert policy.applies_to(reader, perm) is False

    def test_policy_with_condition(self):
        """Policy should evaluate condition"""
        def is_admin(user: User, perm: Permission) -> bool:
            return any(role.name == "admin" for role in user.roles)

        policy = Policy(
            name="admin_only",
            effect=PolicyEffect.ALLOW,
            permissions={Permission("*", "*")},
            condition=is_admin,
        )

        admin = User(user_id="admin1")
        admin.add_role(Roles.admin())

        reader = User(user_id="reader1")
        reader.add_role(Roles.reader())

        perm = Permission("anything", "anything")

        assert policy.applies_to(admin, perm) is True
        assert policy.applies_to(reader, perm) is False


class TestRBACEngine:
    def test_rbac_creation(self):
        """RBACEngine should initialize with default roles"""
        rbac = RBACEngine()

        assert "admin" in rbac._roles
        assert "reader" in rbac._roles
        assert "writer" in rbac._roles
        assert "operator" in rbac._roles

    def test_rbac_create_user(self):
        """RBACEngine should create users"""
        rbac = RBACEngine()

        user = rbac.create_user("user123")

        assert user.user_id == "user123"
        assert rbac.get_user("user123") is user

    def test_rbac_get_nonexistent_user(self):
        """RBACEngine should return None for nonexistent user"""
        rbac = RBACEngine()

        user = rbac.get_user("nonexistent")
        assert user is None

    def test_rbac_delete_user(self):
        """RBACEngine should delete users"""
        rbac = RBACEngine()

        rbac.create_user("user123")
        rbac.delete_user("user123")

        assert rbac.get_user("user123") is None

    def test_rbac_create_role(self):
        """RBACEngine should create roles"""
        rbac = RBACEngine()

        role = rbac.create_role("custom", "Custom role")

        assert role.name == "custom"
        assert rbac.get_role("custom") is role

    def test_rbac_assign_role(self):
        """RBACEngine should assign roles to users"""
        rbac = RBACEngine()

        user = rbac.create_user("user123")
        rbac.assign_role("user123", "reader")

        assert user.can("cache", "read") is True

    def test_rbac_assign_role_nonexistent(self):
        """RBACEngine should fail when assigning nonexistent role"""
        rbac = RBACEngine()

        rbac.create_user("user123")
        result = rbac.assign_role("user123", "nonexistent")

        assert result is False

    def test_rbac_check_permission_with_role(self):
        """RBACEngine should check permissions via roles"""
        rbac = RBACEngine()

        user = rbac.create_user("user123")
        rbac.assign_role("user123", "reader")

        assert rbac.check_permission("user123", "cache", "read") is True
        assert rbac.check_permission("user123", "cache", "write") is False

    def test_rbac_check_permission_nonexistent_user(self):
        """RBACEngine should deny for nonexistent user"""
        rbac = RBACEngine()

        assert rbac.check_permission("nonexistent", "cache", "read") is False

    def test_rbac_add_policy(self):
        """RBACEngine should add policies"""
        rbac = RBACEngine()

        policy = Policy(
            name="deny_cache",
            effect=PolicyEffect.DENY,
            permissions={Permission("cache", "*")},
        )

        rbac.add_policy(policy)

        assert len(rbac.get_policies()) == 1

    def test_rbac_remove_policy(self):
        """RBACEngine should remove policies"""
        rbac = RBACEngine()

        policy = Policy(
            name="test_policy",
            effect=PolicyEffect.ALLOW,
            permissions={Permission("*", "*")},
        )

        rbac.add_policy(policy)
        rbac.remove_policy("test_policy")

        assert len(rbac.get_policies()) == 0

    def test_rbac_policy_allow(self):
        """RBACEngine should allow with ALLOW policy"""
        rbac = RBACEngine()

        user = rbac.create_user("user123")

        policy = Policy(
            name="allow_cache",
            effect=PolicyEffect.ALLOW,
            permissions={Permission("cache", "write")},
            users={"user123"},
        )

        rbac.add_policy(policy)

        assert rbac.check_permission("user123", "cache", "write") is True

    def test_rbac_policy_deny(self):
        """RBACEngine should deny with DENY policy (takes precedence)"""
        rbac = RBACEngine()

        user = rbac.create_user("user123")
        rbac.assign_role("user123", "writer")  # Has write permission

        policy = Policy(
            name="deny_cache",
            effect=PolicyEffect.DENY,
            permissions={Permission("cache", "write")},
            users={"user123"},
        )

        rbac.add_policy(policy)

        # DENY takes precedence over role permission
        assert rbac.check_permission("user123", "cache", "write") is False


class TestRequirePermissionDecorator:
    def test_require_permission_granted(self):
        """require_permission should allow when permission granted"""
        rbac = RBACEngine()

        user = rbac.create_user("user123")
        rbac.assign_role("user123", "reader")

        @require_permission(rbac, "cache", "read")
        def sensitive_operation(user_id: str):
            return "success"

        result = sensitive_operation("user123")
        assert result == "success"

    def test_require_permission_denied(self):
        """require_permission should deny when permission missing"""
        rbac = RBACEngine()

        user = rbac.create_user("user123")
        # No role assigned

        @require_permission(rbac, "cache", "write")
        def sensitive_operation(user_id: str):
            return "success"

        try:
            sensitive_operation("user123")
            assert False, "Should have raised PermissionError"
        except PermissionError as e:
            assert "does not have permission" in str(e)

    def test_require_permission_no_user_id(self):
        """require_permission should error when user_id missing"""
        rbac = RBACEngine()

        @require_permission(rbac, "cache", "read")
        def sensitive_operation():
            return "success"

        try:
            sensitive_operation()
            assert False, "Should have raised PermissionError"
        except PermissionError as e:
            assert "user_id" in str(e)


class TestGlobalRBAC:
    def test_get_rbac_singleton(self):
        """get_rbac should return singleton"""
        rbac1 = get_rbac()
        rbac2 = get_rbac()

        assert rbac1 is rbac2


if __name__ == "__main__":
    import unittest

    suite = unittest.TestLoader().loadTestsFromModule(__import__(__name__))
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    sys.exit(0 if result.wasSuccessful() else 1)
