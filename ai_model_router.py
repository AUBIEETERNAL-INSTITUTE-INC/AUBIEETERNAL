# ai_model_router.py
# Smart model routing for AUBIEETERNAL — thin wrapper over thinking_mode_config

from thinking_mode_config import model_for_mode, router_task_models, system_addon_for_mode


def get_model_for_task(task_type="default"):
    """task_type: default | fast | heavy | synthesis | chat"""
    return router_task_models().get(task_type, router_task_models()["default"])


def get_task_type_for_ui_mode(ui_mode):
    mapping = {
        "Fast": "fast",
        "Balanced": "default",
        "Deep Thinking": "heavy",
        "⚡ Fast": "fast",
        "⚖️ Balanced": "default",
        "🧠 Deep Thinking": "heavy",
    }
    return mapping.get(ui_mode, "default")


def get_model_for_ui_mode(ui_mode):
    return model_for_mode(ui_mode)


def get_system_addon_for_ui_mode(ui_mode):
    return system_addon_for_mode(ui_mode)
