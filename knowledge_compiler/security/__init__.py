#!/usr/bin/env python3
"""
P5-07~P5-08: Security Module - Authentication, RBAC, Audit

Provides authentication, authorization, and audit logging for the system.
"""

from knowledge_compiler.security.auth import (
    AuthMethod,
    AuthResult,
    APIKeyAuth,
    JWTAuth,
    Authenticator,
    get_authenticator,
    get_notion_api_key,
    require_notion_api_key,
)

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

from knowledge_compiler.security.audit import (
    AuditEventType,
    AuditEventStatus,
    AuditEvent,
    AuditLogger,
    get_audit_logger,
    configure_audit_logging,
    audit_operation,
    log_auth_login,
    log_authz_check,
    log_data_operation,
)

# Export main classes
__all__ = [
    # Auth (P5-07)
    "AuthMethod",
    "AuthResult",
    "APIKeyAuth",
    "JWTAuth",
    "Authenticator",
    "get_authenticator",
    "get_notion_api_key",
    "require_notion_api_key",
    # RBAC (P5-07)
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
    # Audit (P5-08)
    "AuditEventType",
    "AuditEventStatus",
    "AuditEvent",
    "AuditLogger",
    "get_audit_logger",
    "configure_audit_logging",
    "audit_operation",
    "log_auth_login",
    "log_authz_check",
    "log_data_operation",
]
