class EValidatorHostMiddleware:
    """
    Za evalidator.eu hostname: rewrite / → /evalidator/
    Ne dirati putanje koje već počinju s /evalidator/ ili /static/
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        host = request.get_host().lower().split(":")[0]
        if host in ("evalidator.eu", "www.evalidator.eu"):
            path = request.path
            skip = ("/evalidator/", "/static/", "/notariat/", "/admin/", "/api/")
            if not any(path.startswith(s) for s in skip):
                new_path = "/evalidator" + (path if path != "/" else "/")
                request.path_info = new_path
                request.path = new_path
        return self.get_response(request)
