from fastapi import Request
from sqladmin import ModelView
from sqladmin.authentication import AuthenticationBackend

from config import get_settings
from database.models import AgentConfig, Report


class AdminAuth(AuthenticationBackend):
    async def login(self, request: Request) -> bool:
        form = await request.form()
        username = form.get("username")
        password = form.get("password")
        settings = get_settings()
        if not settings.admin_password:
            return False
        if username == settings.admin_username and password == settings.admin_password:
            request.session.update({"admin_authenticated": True})
            return True
        return False

    async def logout(self, request: Request) -> bool:
        request.session.clear()
        return True

    async def authenticate(self, request: Request) -> bool:
        return request.session.get("admin_authenticated", False)


class ReportAdmin(ModelView, model=Report):
    name = "Report"
    name_plural = "Reports"
    icon = "fa-solid fa-file-alt"
    column_list = [Report.id, Report.city, Report.start_date, Report.end_date, Report.status, Report.created_at]
    column_searchable_list = [Report.city]
    column_sortable_list = [Report.created_at, Report.status]
    can_create = False
    can_edit = False
    can_delete = False


class AgentConfigAdmin(ModelView, model=AgentConfig):
    name = "Agent Config"
    name_plural = "Agent Configs"
    icon = "fa-solid fa-sliders"
    column_list = [AgentConfig.key, AgentConfig.description, AgentConfig.updated_at]
    column_searchable_list = [AgentConfig.key]
    form_include_pk = True
    can_delete = False
