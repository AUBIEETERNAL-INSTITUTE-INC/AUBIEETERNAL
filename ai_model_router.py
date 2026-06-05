# ai_model_router.py
# Smart model routing for AUBIEETERNAL
# Created: May 26, 2026

def get_model_for_task(task_type="default"):
    """
    Returns the best model based on task type.
    task_type options: "default", "fast", "heavy", "synthesis", "chat"
    """
    models = {
        "default": "qwen2.5:14b",      # Recommended daily driver
        "fast": "qwen2.5:7b",          # Quick responses, Tier-1
        "heavy": "qwen2.5:32b",        # Deep reasoning (occasional)
        "synthesis": "qwen2.5:32b",    # Morning synthesis
        "chat": "qwen2.5:7b",          # Casual chat
    }
    return models.get(task_type, "qwen2.5:14b")


def get_task_type_for_ui_mode(ui_mode):
    """
    Maps UI mode to task type.
    ui_mode: "Fast", "Balanced", "Deep Thinking"
    """
    mapping = {
        "Fast": "fast",
        "Balanced": "default",
        "Deep Thinking": "heavy",
    }
    return mapping.get(ui_mode, "default")