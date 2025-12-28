from miniast import mini_ast, program_ast, type_ast, statement_ast, expression_ast, lvalue_ast


class PPASTVisitor(mini_ast.ASTVisitor):
    def __init__(self):
        self.prefix = []

    def add_prefix(self, is_last):
        if is_last:
            self.prefix.append("   ")
        else:
            self.prefix.append("│  ")

    def remove_prefix(self):
        if self.prefix:
            self.prefix.pop()

    def line(self, text, last):
        if last:
            connector = "└─ "
        else:
            connector = "├─ "
        return "".join(self.prefix) + connector + text

    def Name(self, expr):
        if expr is None:
            return "none"
        if isinstance(expr, expression_ast.IdentifierExpression):
            return expr.id  
        return str(expr)

    def visit_program(self, program: program_ast.Program):
        result = "Program\n"
        
        all_items = []
        for t in program.types:
            all_items.append(t)
        for d in program.declarations:
            all_items.append(d)
        for f in program.functions:
            all_items.append(f)
        
        for i, item in enumerate(all_items):
            last = (i == len(all_items) - 1)
            result += self.line("", last)
            self.add_prefix(last)
            result += item.accept(self)
            self.remove_prefix()
        
        return result

    def visit_type_declaration(self, tdecl: program_ast.TypeDeclaration):
        result = f"TypeDeclaration: {self.Name(tdecl.name)}\n"
        
        for i, field in enumerate(tdecl.fields):
            is_last = (i == len(tdecl.fields) - 1)
            result += self.line("", is_last)
            self.add_prefix(is_last)
            result += field.accept(self)
            self.remove_prefix()
        
        return result

    def visit_declaration(self, decl: program_ast.Declaration):
        type_str = decl.type.accept(self)
        return f"Declaration: {self.Name(decl.name)} : {type_str}\n"

    def visit_function(self, func: program_ast.Function):
        func_name = self.Name(func.name)
        ret_type = func.ret_type.accept(self)
        result = f"Function Name: {func_name}\n"
        
        items = []
        if func.params:
            items.append(('params', func.params))
        if func.locals:
            items.append(('locals', func.locals))
        items.append(('rettype', ret_type))
        if func.body:
            items.append(('body', func.body))
        
        for idx, (label, content) in enumerate(items):
            is_last = (idx == len(items) - 1)
            
            if label == 'rettype':
                result += self.line(f"Return Type: {content}\n", is_last)
            elif label == 'params':
                result += self.line("Parameters\n", is_last)
                self.add_prefix(is_last)
                for i, param in enumerate(content):
                    param_last = (i == len(content) - 1)
                    result += self.line("", param_last)
                    self.add_prefix(param_last)
                    result += param.accept(self)
                    self.remove_prefix()
                self.remove_prefix()
            elif label == 'locals':
                result += self.line("Locals\n", is_last)
                self.add_prefix(is_last)
                for i, local in enumerate(content):
                    local_last = (i == len(content) - 1)
                    result += self.line("", local_last)
                    self.add_prefix(local_last)
                    result += local.accept(self)
                    self.remove_prefix()
                self.remove_prefix()
            else:
                # body
                for i, stmt in enumerate(content):
                    stmt_last = (i == len(content) - 1)
                    final_stmt = is_last and stmt_last
                    result += self.line("", final_stmt)
                    self.add_prefix(final_stmt)
                    result += stmt.accept(self)
                    self.remove_prefix()
        
        return result

    def visit_int_type(self, t): 
        return "int"
    
    def visit_bool_type(self, t): 
        return "bool"

    def visit_struct_type(self, t):
        return f"struct {self.Name(t.name)}"

    def visit_return_type_real(self, t): 
        return "real"
    
    def visit_return_type_void(self, t): 
        return "void"

    def visit_assignment_statement(self, stmt): 
        target_str = stmt.target.accept(self).strip()
        source_str = stmt.source.accept(self).strip()
        result = f"Assignment\n"
        result += self.line(f"Target: {target_str}\n", False)
        result += self.line(f"Source: {source_str}\n", True)
        return result
    
    def visit_block_statement(self, stmt): 
        result = f"Block\n"
        for idx, s in enumerate(stmt.statements):
            is_last = (idx == len(stmt.statements) - 1)
            result += self.line("", is_last)
            self.add_prefix(is_last)
            result += s.accept(self)
            self.remove_prefix()
        return result
    
    def visit_conditional_statement(self, stmt):
        guard_str = stmt.guard.accept(self).strip()
        result = f"ConditionalStatement\n"
        result += self.line(f"Guard: {guard_str}\n", False)
        
        has_else = False
        if hasattr(stmt, 'else_block') and stmt.else_block:
            if isinstance(stmt.else_block, statement_ast.BlockStatement):
                if len(stmt.else_block.statements) > 0:
                    has_else = True
            else:
                has_else = True
        
        result += self.line("ThenBlock\n", not has_else)
        self.add_prefix(not has_else)
        result += self.line("", True)
        self.add_prefix(True)
        result += stmt.then_block.accept(self)
        self.remove_prefix()
        self.remove_prefix()
        
        if has_else:
            result += self.line("ElseBlock\n", True)
            self.add_prefix(True)
            result += self.line("", True)
            self.add_prefix(True)
            result += stmt.else_block.accept(self)
            self.remove_prefix()
            self.remove_prefix()
        
        return result
    
    def visit_while_statement(self, stmt): 
        guard_str = stmt.guard.accept(self).strip()
        result = f"WhileStatement\n"
        result += self.line(f"Guard: {guard_str}\n", False)
        result += self.line("", True)
        self.add_prefix(True)
        result += stmt.body.accept(self)
        self.remove_prefix()
        return result
    
    def visit_delete_statement(self, stmt): 
        expr_str = stmt.expression.accept(self).strip()
        return f"Delete: {expr_str}\n"
    
    def visit_invocation_statement(self, stmt): 
        expr_str = stmt.expression.accept(self).strip()
        return f"InvocationStmt: {expr_str}\n"
    
    def visit_println_statement(self, stmt): 
        expr_str = stmt.expression.accept(self).strip()
        return f"Println: {expr_str}\n"
    
    def visit_print_statement(self, stmt): 
        expr_str = stmt.expression.accept(self).strip()
        return f"Print: {expr_str}\n"
    
    def visit_return_empty_statement(self, stmt):
        return f"Return\n"
    
    def visit_return_statement(self, stmt): 
        expr_str = stmt.expression.accept(self).strip()
        return f"Return: {expr_str}\n"

    def visit_identifier_expression(self, expr):
        return expr.id

    def visit_dot_expression(self, expr):
        left_str = expr.left.accept(self).strip()
        return f"{left_str}.{self.Name(expr.id)}"

    def visit_false_expression(self, expr):
        return "false"
    
    def visit_true_expression(self, expr): 
        return "true"

    def visit_new_expression(self, expr):
        return f"new {self.Name(expr.id)}"

    def visit_null_expression(self, expr): 
        return "null"
    
    def visit_read_expression(self, expr): 
        return "read"

    def visit_integer_expression(self, expr):
        return str(expr.value)

    def visit_invocation_expression(self, expr):
        args_str = ""
        if hasattr(expr, 'arguments') and expr.arguments:
            args_list = [arg.accept(self).strip() for arg in expr.arguments]
            args_str = ", ".join(args_list)
        return f"{self.Name(expr.name)}({args_str})"

    def visit_unary_expression(self, expr):
        operand_str = expr.operand.accept(self).strip()
        op = expr.operator.value
        if op == "!" or op == "-":
            return f"{op}{operand_str}"
        else:
            return f"{op}({operand_str})"

    def visit_binary_expression(self, expr):
        left_str = expr.left.accept(self).strip()
        right_str = expr.right.accept(self).strip()
        return f"({left_str} {expr.operator.value} {right_str})"

    def visit_lvalue_dot(self, lval): 
        left_str = lval.left.accept(self).strip()
        return f"{left_str}.{self.Name(lval.id)}"
    
    def visit_lvalue_id(self, lval): 
        return self.Name(lval.id)