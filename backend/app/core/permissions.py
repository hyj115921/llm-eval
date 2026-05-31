"""
数据隔离与权限控制。
- admin / evaluator: 可查看所有数据
- developer: 只能查看自己创建的数据和所在项目的数据
- viewer: 只能查看已发布的数据
"""


def can_view_all(user_role: str) -> bool:
    """管理员和评测管理员可以查看所有数据"""
    return user_role in ("admin", "evaluator")


def can_manage_data(user_role: str) -> bool:
    """有数据管理权限（创建/修改/删除数据集和指标）"""
    return user_role in ("admin", "evaluator")


def can_execute_task(user_role: str) -> bool:
    """有执行评测和优化的权限"""
    return user_role in ("admin", "evaluator", "developer")


def can_approve(user_role: str) -> bool:
    """有审核权限"""
    return user_role in ("admin", "evaluator")


def can_manage_users(user_role: str) -> bool:
    """有用户管理权限"""
    return user_role == "admin"


def get_visible_statuses(user_role: str) -> list:
    """根据角色返回可见的数据集/指标状态"""
    if user_role in ("admin", "evaluator"):
        return None  # 查看所有状态
    elif user_role == "developer":
        return ["published", "approved", "pending_review"]  # 开发者可见已发布和审核中的数据
    else:  # viewer
        return ["published"]  # 只读用户只能看到已发布的


def filter_by_creator(query, user_id: int, user_role: str):
    """对查询应用创建者过滤（开发者只能看自己的数据）"""
    if user_role in ("admin", "evaluator"):
        return query  # 不限制
    # developer 和 viewer 只能看自己的
    return query.where(query.column_val("created_by") == user_id)
