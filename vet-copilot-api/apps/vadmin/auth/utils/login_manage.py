#!/usr/bin/python
# -*- coding: utf-8 -*-
# @version        : 1.0
# @Create Time    : 2022/8/8 11:02
# @File           : auth_util.py
# @IDE            : PyCharm
# @desc           : 简要说明

from datetime import datetime, timedelta
from typing import Optional
from fastapi import Request
from application import settings
import jwt
from apps.vadmin.auth import models
from core.database import redis_getter
from utils.sms.code import CodeSMS
from .validation import LoginValidation, LoginForm, LoginResult


class LoginManage:
    """
    登录认证工具
    """

    @LoginValidation
    async def password_login(self, data: LoginForm, user: models.VadminUser, **kwargs) -> LoginResult:
        """
        验证用户密码
        """
        result = models.VadminUser.verify_password(data.password, user.password)
        if result:
            return LoginResult(status=True, msg="验证成功")
        return LoginResult(status=False, msg="手机号或密码错误")

    @LoginValidation
    async def sms_login(self, data: LoginForm, request: Request, **kwargs) -> LoginResult:
        """
        验证用户短信验证码
        """
        rd = redis_getter(request)
        sms = CodeSMS(data.telephone, rd)
        result = await sms.check_sms_code(data.password)
        if result:
            return LoginResult(status=True, msg="验证成功")
        return LoginResult(status=False, msg="验证码错误")

    @staticmethod
    def build_token_payload(
        user: models.VadminUser,
        is_refresh: bool = False,
        tenant_id: Optional[int] = None,
        hospital_id: Optional[int] = None
    ) -> dict:
        """
        构建 Token payload，与 vet-platform 兼容

        Token 结构:
        {
            "sub": telephone,        # 主标识（手机号）
            "user_id": int,          # 用户ID
            "tenant_id": int|None,   # 租户ID（vet-copilot 无此概念，默认 None）
            "hospital_id": int|None, # 分院ID（vet-copilot 无此概念，默认 None）
            "role": str,             # 用户角色
            "permissions": list,     # 权限列表
            "is_platform_admin": bool,  # 是否平台管理员
            "is_refresh": bool,      # 是否为刷新令牌
            "password": str,         # 密码哈希（用于验证）
        }
        """
        # 确定角色
        if user.is_admin():
            role = "platform_admin"
        elif user.is_staff:
            role = "staff"
        else:
            role = "user"

        # 获取权限列表
        permissions = []
        if user.is_admin():
            permissions = ["*.*.*"]
        else:
            for role_obj in user.roles:
                for menu in role_obj.menus:
                    if menu.perms and not menu.disabled:
                        permissions.append(menu.perms)

        return {
            "sub": user.telephone,
            "user_id": user.id,
            "tenant_id": tenant_id,
            "hospital_id": hospital_id,
            "role": role,
            "permissions": permissions,
            "is_platform_admin": user.is_admin(),
            "is_refresh": is_refresh,
            "password": user.password,
        }

    @staticmethod
    def create_token(payload: dict, expires: timedelta = None):
        """
        创建一个生成新的访问令牌的工具函数。

        pyjwt：https://github.com/jpadilla/pyjwt/blob/master/docs/usage.rst
        jwt 博客：https://geek-docs.com/python/python-tutorial/j_python-jwt.html

        #TODO 传入的时间为UTC时间datetime.datetime类型，但是在解码时获取到的是本机时间的时间戳

        使用 RS256 非对称加密：私钥签名，公钥验证
        """
        if expires:
            expire = datetime.utcnow() + expires
        else:
            expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        payload.update({"exp": expire})
        # 使用私钥进行签名
        encoded_jwt = jwt.encode(payload, settings.PRIVATE_KEY, algorithm=settings.ALGORITHM)
        return encoded_jwt
