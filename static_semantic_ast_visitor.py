from miniast import mini_ast, program_ast, type_ast, statement_ast, expression_ast, lvalue_ast

# Type constants
INT = ("int",)
BOOL = ("bool",)
VOID = ("void",)
NULL = ("null",)

class SymbolTable:
    def __init__(self, parent=None, scope_name="Global"):
        self.parent = parent
        self.symbols = {}
        self.scope_name = scope_name

    def define(self, name, value, linenum, analyzer):
        if name in self.symbols:
            analyzer.Error(f"Redeclaration of '{name}'", linenum)
        else:
            self.symbols[name] = value

    def keys(self):
        return self.symbols.keys()
    def lookupTable(self, name):
        scope = self
        while scope:
            if name in scope.symbols:
                return scope.symbols[name]
            scope = scope.parent
        return None


    def lookup_local(self, name):
        return self.symbols.get(name)

    def print_all_scopes(self, analyzer):
        print("SYMBOL TABLE \n")
        
        # Print structs
        if analyzer.structs:
            print("\nSTRUCTS:")
            for name, decl in sorted(analyzer.structs.items()):
                print(f"  {name} ")
                if decl.fields:
                    for f in decl.fields:
                        fname = f.name.id if getattr(f.name, 'id') else str(f.name)
                        ftype = self.Type(f.type)
                        print(f"     {fname}: {ftype}")
        else:
            print("[empty]")
        print("\nGLOBAL SCOPE:")
        if self.symbols:
            for name, value in sorted(self.symbols.items()):
                gtype = self.Type(value.type) if getattr(value, 'type') else '?'
                print(f"  {name}: {gtype}")
        else:
            print("  [empty]")
        
        if analyzer.function_scopes:
            print("\nFUNCTION SCOPES:")
            for func_name in sorted(analyzer.function_scopes.keys()):
                func_scope = analyzer.function_scopes[func_name]
                func = analyzer.functions[func_name]
                ret = self.Type(func.ret_type)
                
                print(f"\n  Scope: {func_name}()")
                print(f"    Return type: {ret}")
                print(f"    Symbols in this scope:")
                
                if func_scope.symbols:
                    for name, value in sorted(func_scope.symbols.items()):
                        vtype = self.Type(value.type) if getattr(value, 'type') else '?'
                        param = False
                        for p in func.params:
                                if self.Name(p.name) == name:
                                    param = True
                                    break

                        kind = "parameter" if param else "local"
                        print(f"      {name}: {vtype} ({kind})")
                else:
                    print("      [empty]")
    def Name(self, ident):
        if ident is None:
            return "none"
        if hasattr(ident, "id"):
            return ident.id
        return str(ident)

    def Type(self, node):
        if node is None:
            return "None"
        tname = type(node).__name__
        if 'Int' in tname:
            return "int"
        if 'Bool' in tname:
            return "bool"
        if 'Void' in tname:
            return "void"
        if 'Struct' in tname and hasattr(node, 'name'):
            sname = node.name.id if hasattr(node.name, 'id') else str(node.name)
            return f"struct {sname}"
        if 'ReturnType' in tname and hasattr(node, 'type_'):
            return self.Type(node.type_)
        return tname


class SemanticAnalyzer(mini_ast.ASTVisitor):
    def __init__(self):
        self.errors = 0
        self.globals = SymbolTable(scope_name="Global")
        self.functions = {}
        self.structs = {}
        self.function_scopes = {}  
        
        # Current scope context
        self.current_scope = self.globals
        self.current_function = None

    def analyze(self, program: program_ast.Program):
        program.accept(self)
        print(f"ERRORS FOUND {self.errors}")
        return self.errors

    def Error(self, message: str, linenum: int):
        print(f"ERROR. {message} #{linenum}")
        self.errors += 1

    def Name(self, ident):
        if ident is None:
            return "None"
        if getattr(ident, "id"):
            return ident.id
        return str(ident)

    def Type(self, node):
        if node is None:
            return None
        if isinstance(node, type_ast.IntType):
            return INT
        if isinstance(node, type_ast.BoolType):
            return BOOL
        if isinstance(node, type_ast.ReturnTypeVoid):
            return VOID
        if isinstance(node, type_ast.ReturnTypeReal):
            return self.Type(node.type_)
        if isinstance(node, type_ast.StructType):
            name = getattr(node, "name", getattr(node, "id", None))
            sname = self.Name(name)
            if sname not in self.structs:
                return None
            return ("struct", sname)
        return None

    def _is_struct(self, t):
        return isinstance(t, tuple) and len(t) == 2 and t[0] == "struct"

    def _types_match(self, a, b):
        if a is None or b is None:
            return False
        if b == NULL and self._is_struct(a):
            return True
        return a == b

    def visit_program(self, program: program_ast.Program):
        for t in program.types:
            name = self.Name(t.name)
            if name in self.structs:
                self.Error(f"Duplicate struct '{name}'", t.linenum)
            else:
                self.structs[name] = t
            t.accept(self)
        #for global variables 
        for decl in program.declarations:
            dname = self.Name(decl.name)
            if self.globals.lookup_local(dname):
                self.Error(f"Duplicate global '{dname}'", decl.linenum)
            else:
                self.globals.define(dname, decl, decl.linenum, self)
            
            t = self.Type(decl.type)
            if t is None and isinstance(decl.type, type_ast.StructType):
                sname = self.Name(decl.type.name)
                self.Error(f"Undefined struct '{sname}'", decl.linenum)
            decl.type.accept(self)
        #register functions
        for func in program.functions:
            fname = self.Name(func.name)
            if fname in self.functions:
                self.Error(f"Duplicate function '{fname}'", func.linenum)
            else:
                self.functions[fname] = func

        # Check functions
        for func in program.functions:
            func.accept(self)

        # Check main
        main_fn = self.functions.get("main")
        if main_fn is None:
            self.Error("Main() function id missing", 0)
        else:
            if len(main_fn.params) != 0:
                self.Error("main() function takes no arguments", main_fn.linenum)
            if self.Type(main_fn.ret_type) != INT:
                self.Error("main() must return an int", main_fn.linenum)

    def visit_type_declaration(self, tdecl: program_ast.TypeDeclaration):
        seen = set()
        struct_name = self.Name(tdecl.name)
        for f in tdecl.fields:
            fname = self.Name(f.name)
            if fname in seen:
                self.Error(f"Duplicate field of name: '{fname}'", f.linenum)
            else:
                seen.add(fname)
            
            ft = self.Type(f.type)
            if ft is None and isinstance(f.type, type_ast.StructType):
                sname = self.Name(f.type.name)
                if sname != struct_name and sname not in self.structs:
                    self.Error(f"Undefined struct of name: '{sname}'", f.linenum)

    def visit_declaration(self, decl: program_ast.Declaration):
        return None

    def visit_function(self, func: program_ast.Function):
        fname = self.Name(func.name)
        
        # Save current scope and create new function scope
        prev_scope = self.current_scope
        prev_function = self.current_function
        
        # Create function scope with global as parent
        func_scope = SymbolTable(parent=self.globals, scope_name=f"{fname}()")
        self.current_scope = func_scope
        self.current_function = func
        self.function_scopes[fname] = func_scope

        # Add parameters to function scope
        for p in func.params:
            pname = self.Name(p.name)
            if func_scope.lookup_local(pname):
                self.Error(f"Duplicate parameter of name: '{pname}'", p.linenum)
            else:
                func_scope.define(pname, p, p.linenum, self)
            
            pt = self.Type(p.type)
            if pt is None and isinstance(p.type, type_ast.StructType):
                sname = self.Name(p.type.name)
                if sname not in self.structs:
                    self.Error(f"Undefined struct of name'{sname}'", p.linenum)

        # Add locals to function scope
        for l in func.locals:
            lname = self.Name(l.name)
            if func_scope.lookup_local(lname):
                self.Error(f"Duplicate local of the name: '{lname}'", l.linenum)
            else:
                func_scope.define(lname, l, l.linenum, self)
            
            lt = self.Type(l.type)
            if lt is None and isinstance(l.type, type_ast.StructType):
                sname = self.Name(l.type.name)
                if sname not in self.structs:
                    self.Error(f"Undefined struct of name: '{sname}'", l.linenum)

        # Visit body with function scope active
        for s in func.body:
            s.accept(self)
        #return check
        declared = self.Type(func.ret_type)
        if func.body:
            last = func.body[-1]
            if isinstance(last, statement_ast.ReturnEmptyStatement):
                if declared != VOID:
                    self.Error(f"Non-void function must return value", last.linenum)
            elif isinstance(last, statement_ast.ReturnStatement):
                if last.expression:
                    et = self._expr_type(last.expression)
                    if et and declared == VOID:
                        self.Error(f"Void function cannot return value", last.linenum)
                    elif et and not self._types_match(declared, et):
                        self.Error(f"Return type mismatch", last.linenum)
                elif declared != VOID:
                    self.Error(f"Non-void function must return value", last.linenum)
            else:
                if declared != VOID:
                    self.Error(f"Missing return statement", func.linenum)
        elif declared != VOID:
            self.Error(f"Missing return statement", func.linenum)
        # Restore previous scope
        self.current_scope = prev_scope
        self.current_function = prev_function

    def visit_int_type(self, t):
        return INT
    
    def visit_bool_type(self, t):
        return BOOL

    def visit_struct_type(self, t):
        sname = self.Name(t.name if getattr(t, "name") else t.id if getattr(t, "id") else None)
        if sname not in self.structs:
            self.Error(f"Undefined struct of name'{sname}'", t.linenum)
            return None
        return ("struct", sname)

    def visit_return_type_real(self, t):
        return self.Type(t.type_)

    def visit_return_type_void(self, t):
        return VOID

    def visit_block_statement(self, stmt):
        for s in stmt.statements:
            s.accept(self)
        return None

    def visit_assignment_statement(self, stmt):
        lhs_t = self._lvalue_type(stmt.target)
        rhs_t = self._expr_type(stmt.source)
        if lhs_t and rhs_t and not self._types_match(lhs_t, rhs_t):
            self.Error("Type mismatch in assignment", stmt.linenum)
        return None

    def visit_conditional_statement(self, stmt):
        cond_t = self._expr_type(stmt.guard)
        if cond_t and cond_t != BOOL:
            self.Error("Condition must be a boolean", stmt.linenum)
        stmt.then_block.accept(self)
        if stmt.else_block and not getattr(stmt.else_block, "statements", []):
            stmt.else_block = None
        elif stmt.else_block:
            stmt.else_block.accept(self)
        return None


    def visit_while_statement(self, stmt):
        cond_t = self._expr_type(stmt.guard)
        if cond_t and cond_t != BOOL:
            self.Error("Condition must be boolean", stmt.linenum)
        stmt.body.accept(self)
        return None

    def visit_delete_statement(self, stmt):
        t = self._expr_type(stmt.expression)
        if t and not self._is_struct(t):
            self.Error("delete requires a struct", stmt.linenum)
        return None

    def visit_invocation_statement(self, stmt):
        self._expr_type(stmt.expression)
        return None

    def visit_println_statement(self, stmt):
        t = self._expr_type(stmt.expression)
        if t != INT:
            self.Error("print requires int", stmt.linenum)
        return None

    def visit_print_statement(self, stmt):
        t = self._expr_type(stmt.expression)
        if t != INT:
            self.Error("print requires int", stmt.linenum)
        return None

    def visit_return_empty_statement(self, stmt):
        if self.current_function:
            declared = self.Type(self.current_function.ret_type)
            if declared != VOID:
                self.Error("Non-void function must return value", stmt.linenum)
        return None

    def visit_return_statement(self, stmt):
        if not self.current_function:
            return None
        declared = self.Type(self.current_function.ret_type)
        if stmt.expression:
            et = self._expr_type(stmt.expression)
            if declared == VOID:
                self.Error(" a Void function cannot return value", stmt.linenum)
            elif et and not self._types_match(declared, et):
                self.Error("Return type mismatch", stmt.linenum)
        elif declared != VOID:
            self.Error("Non-void function must return value", stmt.linenum)
        return None

    def visit_integer_expression(self, expr):
        return INT

    def visit_true_expression(self, expr):
        return BOOL

    def visit_false_expression(self, expr):
        return BOOL

    def visit_null_expression(self, expr):
        return NULL

    def visit_read_expression(self, expr):
        return INT

    def visit_identifier_expression(self, expr):
        name = expr.id
        # Look up in current scope (uses lexical scoping chain)
        decl = self.current_scope.lookupTable(name)
        if decl:
            return self.Type(decl.type)
        self.Error(f"Undefined variable '{name}'", expr.linenum)
        return None

    def visit_dot_expression(self, expr):
        left_t = self._expr_type(expr.left)
        if not left_t or not self._is_struct(left_t):
            if left_t:
                self.Error("Dot operator requires struct", expr.linenum)
            return None
        struct_name = left_t[1]
        struct_decl = self.structs.get(struct_name)
        if not struct_decl:
            return None
        field_name = self.Name(expr.id)
        for fld in struct_decl.fields:
            if self.Name(fld.name) == field_name:
                return self.Type(fld.type)
        self.Error(f"Struct {struct_name} has no field '{field_name}'", expr.linenum)
        return None

    def visit_new_expression(self, expr):
        sname = self.Name(expr.id)
        if sname not in self.structs:
            self.Error(f"Undefined struct '{sname}'", expr.linenum)
            return None
        return ("struct", sname)

    def visit_invocation_expression(self, expr):
        fname = self.Name(expr.name)
        fn = self.functions.get(fname)
        if not fn:
            self.Error(f"Undefined function '{fname}'", expr.linenum)
            return None
        expected = len(fn.params) if fn.params else 0
        given = len(expr.arguments) if expr.arguments else 0
        if expected != given:
            self.Error(f"Wrong number of arguments to '{fname}'", expr.linenum)
        for arg_expr, param_decl in zip(expr.arguments or [], fn.params or []):
            at = self._expr_type(arg_expr)
            pt = self.Type(param_decl.type)
            if at and pt:
                if at == NULL and not self._is_struct(pt):
                    self.Error("Cannot pass null to non-struct", arg_expr.linenum)
                elif at != pt and at != NULL:
                    self.Error(f"Argument type mismatch", arg_expr.linenum)
        return self.Type(fn.ret_type)

    def visit_unary_expression(self, expr):
        op = expr.operator if hasattr(expr, "operator") else expr.op if hasattr(expr, "op") else None
        operand_t = self._expr_type(expr.operand)
        if not operand_t:
            return None
        op_val = op.value if hasattr(op, "value") else str(op)
        if op_val == "!":
            if operand_t != BOOL:
                self.Error(" requires boolean", expr.linenum)
            return BOOL
        if op_val == "-":
            if operand_t != INT:
                self.Error("requires int", expr.linenum)
            return INT
        return None

    def visit_binary_expression(self, expr):
        lhs_expr = getattr(expr, "lhs", None) or getattr(expr, "left", None)
        rhs_expr = getattr(expr, "rhs", None) or getattr(expr, "right", None)
        left_t = self._expr_type(lhs_expr)
        right_t = self._expr_type(rhs_expr)
        if not left_t or not right_t:
            return None
        op = expr.operator if hasattr(expr, "operator") else expr.op if hasattr(expr, "op") else None
        op_val = op.value if hasattr(op, "value") else str(op)
        
        if op_val in ("*", "/", "+", "-"):
            if left_t != INT or right_t != INT:
                self.Error("Arithmetic requires int operands", expr.linenum)
            return INT
        if op_val in ("<", ">", "<=", ">="):
            if left_t != INT or right_t != INT:
                self.Error("Comparison requires int operands", expr.linenum)
            return BOOL
        if op_val in ("==", "!="):
            if left_t == NULL:
                if not self._is_struct(right_t):
                    self.Error("Cannot compare null with non-struct", expr.linenum)
            elif right_t == NULL:
                if not self._is_struct(left_t):
                    self.Error("Cannot compare null with non-struct", expr.linenum)
            elif left_t != right_t:
                self.Error("Equality requires matching types", expr.linenum)
            return BOOL
        if op_val in ("&&", "||"):
            if left_t != BOOL or right_t != BOOL:
                self.Error("Boolean operators require boolean operands", expr.linenum)
            return BOOL
        return None

    def visit_lvalue_id(self, lval):
        name_obj = None
        for a in ("identifier", "id", "name"):
            if hasattr(lval, a):
                name_obj = getattr(lval, a)
                break
        nm = name_obj.id if isinstance(name_obj, expression_ast.IdentifierExpression) else str(name_obj)
        
        # Look up in current scope (uses lexical scoping chain)
        decl = self.current_scope.lookupTable(nm)
        if decl:
            return self.Type(decl.type)
        self.Error(f"Undefined variable '{nm}'", lval.linenum)
        return None

    def visit_lvalue_dot(self, lval):
        left_expr = getattr(lval, "lhs", None)
        left_t = self._expr_type(left_expr)
        if not left_t or not self._is_struct(left_t):
            if left_t:
                self.Error("Dot operator requires struct", lval.linenum)
            return None
        sname = left_t[1]
        struct_decl = self.structs.get(sname)
        if not struct_decl:
            return None
        name_obj = None
        for a in ("identifier", "id", "name"):
            if hasattr(lval, a):
                name_obj = getattr(lval, a)
                break
        field_name = self.Name(name_obj)
        for fld in struct_decl.fields:
            if self.Name(fld.name) == field_name:
                return self.Type(fld.type)
        self.Error(f"Field '{field_name}' not found", lval.linenum)
        return None

    def _expr_type(self, expr):
        if expr is None:
            return None
        return expr.accept(self)

    def _lvalue_type(self, lval):
        if lval is None:
            return None
        return lval.accept(self)