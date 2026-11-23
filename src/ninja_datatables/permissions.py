from functools import wraps

from django.http import JsonResponse

# HTTP method -> Django's default model-permission action.
_METHOD_ACTION = {
    "GET": "view",
    "POST": "add",
    "PUT": "change",
    "PATCH": "change",
    "DELETE": "delete",
}


def require_model_perm(model, action=None):
    """View decorator requiring the standard Django permission for `model`
    (`<app_label>.<action>_<model_name>`), answering 401/403 JSON otherwise.

    The action is inferred from the HTTP method (GET->view, POST->add,
    PUT/PATCH->change, DELETE->delete) unless given explicitly. Meant to be
    applied with `ninja.decorators.decorate_view`, which runs it before the
    router's `auth`, so anonymous requests are answered with 401 here."""

    def decorator(func):
        @wraps(func)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return JsonResponse({"detail": "Unauthorized"}, status=401)
            act = action or _METHOD_ACTION.get(request.method, "view")
            perm = f"{model._meta.app_label}.{act}_{model._meta.model_name}"
            if not request.user.has_perm(perm):
                return JsonResponse({"detail": "Permission denied"}, status=403)
            return func(request, *args, **kwargs)

        return wrapper

    return decorator
