def latex_to_ast(latex: str) -> str | None:
    try:
        from sympy.parsing.latex import parse_latex
        import sympy as sp
        expr = parse_latex(latex)
        return sp.srepr(expr)
    except Exception:
        return None