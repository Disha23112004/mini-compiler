from miniast import mini_ast, program_ast, type_ast, statement_ast, expression_ast, lvalue_ast

class CodeGenVisitor(mini_ast.ASTVisitor):
    """Generate RISC-V assembly code from Mini AST."""
    
    def __init__(self):
        self.output = []
        self.label_counter = 0
        self.structs = {}  # struct_name -> {field_name: offset}
        self.globals = {}  # var_name -> label
        self.locals = {}   # var_name -> offset from fp
        self.current_function = None
        self.stack_offset = 0
        self.read = False
        self.type_environment = {}  # Track types of variables for struct field access
        self.current_locals_size = 0  # Track current function's local variable space
        
    def emit(self, instruction):
        """Add an instruction to the output."""
        self.output.append(instruction)
    
    def Label(self, prefix="L"):
        """Generate a unique label."""
        label = f"{prefix}{self.label_counter}"
        self.label_counter += 1
        return label
    
    def Name(self, expr):
        """Extract name from identifier expression."""
        if expr is None:
            return "none"
        if isinstance(expr, expression_ast.IdentifierExpression):
            return expr.id
        return str(expr)
    
    def get_code(self):
        """Return the complete assembly code."""
        return "\n".join(self.output)
    
    # =========== Program Structure ===========
    
    def visit_program(self, program: program_ast.Program):
        """Generate assembly for entire program."""
        # Calculate struct layouts
        for tdecl in program.types:
            self._calculate_struct_layout(tdecl)
        
        # Build type environment for globals
        for decl in program.declarations:
            name = self.Name(decl.name)
            self.type_environment[name] = decl.type
        
        # Emit file header
        self.emit(".globl main")
        
        # Import berkeley_utils first (required by read_int)
        self.emit(".import berkeley_utils.s")
        
        # Check if we need read functionality
        self.read = self._check_for_read(program)
        if self.read:
            self.emit(".import read_int.s")
        
        self.emit("")
        self.emit(".data")
        
        # Emit input file pointer if needed
        if self.read:
            self.emit("input_file_ptr: .space 4")
        
        # Emit global variables
        for decl in program.declarations:
            name = self.Name(decl.name)
            label = f"global_{name}"
            self.globals[name] = label
            size = self._type_size(decl.type)
            self.emit(f"{label}: .space {size}")
        
        self.emit("")
        self.emit(".text")
        self.emit("")
        
        # Generate code for all functions
        for func in program.functions:
            func.accept(self)
        
        return None
    
    def _check_for_read(self, program):
        """Check if program uses read statement."""
        # Simple recursive checker that doesn't inherit from ASTVisitor
        def check_expr(expr):
            if expr is None:
                return False
            if isinstance(expr, expression_ast.ReadExpression):
                return True
            if isinstance(expr, expression_ast.BinaryExpression):
                return check_expr(expr.left) or check_expr(expr.right)
            if isinstance(expr, expression_ast.UnaryExpression):
                return check_expr(expr.operand)
            if isinstance(expr, expression_ast.DotExpression):
                return check_expr(expr.left)
            if isinstance(expr, expression_ast.InvocationExpression):
                return any(check_expr(arg) for arg in expr.arguments)
            return False
        
        def check_stmt(stmt):
            if stmt is None:
                return False
            if isinstance(stmt, statement_ast.AssignmentStatement):
                return check_expr(stmt.source)
            if isinstance(stmt, statement_ast.BlockStatement):
                return any(check_stmt(s) for s in stmt.statements)
            if isinstance(stmt, statement_ast.ConditionalStatement):
                return (check_expr(stmt.guard) or 
                       check_stmt(stmt.then_block) or 
                       check_stmt(stmt.else_block))
            if isinstance(stmt, statement_ast.WhileStatement):
                return check_expr(stmt.guard) or check_stmt(stmt.body)
            if isinstance(stmt, statement_ast.PrintStatement):
                return check_expr(stmt.expression)
            if isinstance(stmt, statement_ast.PrintLnStatement):
                return check_expr(stmt.expression)
            if isinstance(stmt, statement_ast.ReturnStatement):
                return check_expr(stmt.expression)
            if isinstance(stmt, statement_ast.DeleteStatement):
                return check_expr(stmt.expression)
            if isinstance(stmt, statement_ast.InvocationStatement):
                return check_expr(stmt.expression)
            return False
        
        # Check all functions
        for func in program.functions:
            for stmt in func.body:
                if check_stmt(stmt):
                    return True
        return False
    
    def _calculate_struct_layout(self, tdecl: program_ast.TypeDeclaration):
        """Calculate field offsets for a struct type."""
        name = self.Name(tdecl.name)
        layout = {}
        offset = 0
        
        for field in tdecl.fields:
            fname = self.Name(field.name)
            layout[fname] = offset
            offset += self._type_size(field.type)
        
        self.structs[name] = {"fields": layout, "size": offset}
    
    def _type_size(self, type_node):
        """Return size in bytes for a type."""
        if isinstance(type_node, type_ast.IntType):
            return 4
        elif isinstance(type_node, type_ast.BoolType):
            return 4
        elif isinstance(type_node, type_ast.StructType):
            # Struct types in fields are always pointers (4 bytes)
            return 4
        return 4
    
    # =========== Functions ===========
    
    def visit_function(self, func: program_ast.Function):
        """Generate assembly for a function."""
        fname = self.Name(func.name)
        self.current_function = fname
        self.locals = {}
        self.stack_offset = 0
        
        # Build type environment for parameters and locals
        local_type_env = {}
        for param in func.params:
            pname = self.Name(param.name)
            local_type_env[pname] = param.type
        for local in func.locals:
            lname = self.Name(local.name)
            local_type_env[lname] = local.type
        self.type_environment.update(local_type_env)
        
        # Function label
        self.emit(f"{fname}:")
        
        # Prologue
        self.emit("    addi sp, sp, -8")
        self.emit("    sw ra, 4(sp)")
        self.emit("    sw fp, 0(sp)")
        self.emit("    addi fp, sp, 0")
        
        # Handle main function with command line args
        if fname == "main" and self.read:
            self.emit("    # Save input filename")
            self.emit("    lw t0, 4(a1)")
            self.emit("    la t1, input_file_ptr")
            self.emit("    sw t0, 0(t1)")
        
        # Allocate space for locals and parameters
        total_locals_size = 0
        current_offset = 0
        
        # Parameters (passed in registers, save to stack)
        for i, param in enumerate(func.params):
            pname = self.Name(param.name)
            size = self._type_size(param.type)
            current_offset += size
            self.locals[pname] = -current_offset
            total_locals_size += size
        
        # Local variables
        for local in func.locals:
            lname = self.Name(local.name)
            size = self._type_size(local.type)
            current_offset += size
            self.locals[lname] = -current_offset
            total_locals_size += size
        
        # Store the total locals size for use in return statements
        self.current_locals_size = total_locals_size
        
        # Allocate stack space FIRST
        if total_locals_size > 0:
            self.emit(f"    addi sp, sp, -{total_locals_size}")
        
        # THEN save parameter registers to stack
        for i, param in enumerate(func.params):
            if i < 8:  # a0-a7
                pname = self.Name(param.name)
                offset = self.locals[pname]
                self.emit(f"    sw a{i}, {offset}(fp)")
        
        # Generate function body
        for stmt in func.body:
            stmt.accept(self)
        
        # If no explicit return, add default for main
        if fname == "main":
            if not func.body or not isinstance(func.body[-1], (statement_ast.ReturnStatement, statement_ast.ReturnEmptyStatement)):
                self.emit("    # Implicit return from main")
                if total_locals_size > 0:
                    self.emit(f"    addi sp, sp, {total_locals_size}")
                self.emit("    lw fp, 0(sp)")
                self.emit("    lw ra, 4(sp)")
                self.emit("    addi sp, sp, 8")
                self.emit("    li a0, 0")
                self.emit("    jal exit")
        else:
            if not func.body or not isinstance(func.body[-1], (statement_ast.ReturnStatement, statement_ast.ReturnEmptyStatement)):
                self.emit("    # Implicit return")
                if total_locals_size > 0:
                    self.emit(f"    addi sp, sp, {total_locals_size}")
                self.emit("    lw fp, 0(sp)")
                self.emit("    lw ra, 4(sp)")
                self.emit("    addi sp, sp, 8")
                self.emit("    jr ra")
        
        self.emit("")
        self.current_function = None
        
        # Clean up local type environment
        for key in local_type_env:
            if key in self.type_environment:
                del self.type_environment[key]
    
    # =========== Statements ===========
    
    def visit_block_statement(self, stmt: statement_ast.BlockStatement):
        """Generate code for a block of statements."""
        for s in stmt.statements:
            s.accept(self)
        return None
    
    def visit_assignment_statement(self, stmt: statement_ast.AssignmentStatement):
        """Generate code for assignment: target = source."""
        # Evaluate source expression into t0
        stmt.source.accept(self)
        self.emit("    mv t1, t0  # Save result")
        
        # Get address of target into t0
        self._generate_lvalue_address(stmt.target)
        
        # Store value at address
        self.emit("    sw t1, 0(t0)")
        return None
    
    def visit_print_statement(self, stmt: statement_ast.PrintStatement):
        """Generate code for print statement."""
        stmt.expression.accept(self)
        self.emit("    mv a0, t0")
        self.emit("    jal print_int")
        return None
    
    def visit_println_statement(self, stmt: statement_ast.PrintLnStatement):
        """Generate code for println statement."""
        stmt.expression.accept(self)
        self.emit("    mv a0, t0")
        self.emit("    jal print_int")
        self.emit("    li a0, '\\n'")
        self.emit("    jal print_char")
        return None
    
    def visit_conditional_statement(self, stmt: statement_ast.ConditionalStatement):
        """Generate code for if-then-else."""
        else_label = self.Label("else")
        end_label = self.Label("endif")
        
        # Evaluate condition
        stmt.guard.accept(self)
        
        # Branch if false
        self.emit(f"    beq t0, zero, {else_label}")
        
        # Then block
        stmt.then_block.accept(self)
        self.emit(f"    j {end_label}")
        
        # Else block
        self.emit(f"{else_label}:")
        if stmt.else_block and hasattr(stmt.else_block, 'statements') and stmt.else_block.statements:
            stmt.else_block.accept(self)
        
        self.emit(f"{end_label}:")
        return None
    
    def visit_while_statement(self, stmt: statement_ast.WhileStatement):
        """Generate code for while loop."""
        start_label = self.Label("while_start")
        end_label = self.Label("while_end")
        
        self.emit(f"{start_label}:")
        
        # Evaluate condition
        stmt.guard.accept(self)
        self.emit(f"    beq t0, zero, {end_label}")
        
        # Loop body
        stmt.body.accept(self)
        self.emit(f"    j {start_label}")
        
        self.emit(f"{end_label}:")
        return None
    
    def visit_delete_statement(self, stmt: statement_ast.DeleteStatement):
        """Generate code for delete statement (free memory)."""
        stmt.expression.accept(self)
        # In a real implementation, call free
        # For now, just evaluate the expression
        return None
    
    def visit_return_statement(self, stmt: statement_ast.ReturnStatement):
        """Generate code for return with value."""
        stmt.expression.accept(self)
        self.emit("    mv a0, t0")
        
        # Epilogue - use stored locals size
        if self.current_locals_size > 0:
            self.emit(f"    addi sp, sp, {self.current_locals_size}")
        self.emit("    lw fp, 0(sp)")
        self.emit("    lw ra, 4(sp)")
        self.emit("    addi sp, sp, 8")
        
        # For main, exit cleanly
        if self.current_function == "main":
            self.emit("    jal exit")
        else:
            self.emit("    jr ra")
        return None
    
    def visit_return_empty_statement(self, stmt: statement_ast.ReturnEmptyStatement):
        """Generate code for return without value."""
        # Epilogue - use stored locals size
        if self.current_locals_size > 0:
            self.emit(f"    addi sp, sp, {self.current_locals_size}")
        self.emit("    lw fp, 0(sp)")
        self.emit("    lw ra, 4(sp)")
        self.emit("    addi sp, sp, 8")
        
        # For main, exit cleanly
        if self.current_function == "main":
            self.emit("    li a0, 0")
            self.emit("    jal exit")
        else:
            self.emit("    jr ra")
        return None
    
    def visit_invocation_statement(self, stmt: statement_ast.InvocationStatement):
        """Generate code for function call as statement."""
        stmt.expression.accept(self)
        return None
    
    # =========== Expressions ===========
    
    def visit_integer_expression(self, expr: expression_ast.IntegerExpression):
        """Load integer constant into t0."""
        self.emit(f"    li t0, {expr.value}")
        return None
    
    def visit_true_expression(self, expr: expression_ast.TrueExpression):
        """Load true (1) into t0."""
        self.emit("    li t0, 1")
        return None
    
    def visit_false_expression(self, expr: expression_ast.FalseExpression):
        """Load false (0) into t0."""
        self.emit("    li t0, 0")
        return None
    
    def visit_null_expression(self, expr: expression_ast.NullExpression):
        """Load null (0) into t0."""
        self.emit("    li t0, 0")
        return None
    
    def visit_read_expression(self, expr: expression_ast.ReadExpression):
        """Generate code for read statement."""
        self.emit("    la t0, input_file_ptr")
        self.emit("    lw a0, 0(t0)")
        self.emit("    jal read_int")
        self.emit("    mv t0, a0")
        return None
    
    def visit_identifier_expression(self, expr: expression_ast.IdentifierExpression):
        """Load variable value into t0."""
        name = expr.id
        
        if name in self.locals:
            # Local variable or parameter
            offset = self.locals[name]
            self.emit(f"    lw t0, {offset}(fp)")
        elif name in self.globals:
            # Global variable
            label = self.globals[name]
            self.emit(f"    la t1, {label}")
            self.emit(f"    lw t0, 0(t1)")
        else:
            self.emit(f"    # ERROR: Unknown variable {name}")
            self.emit("    li t0, 0")
        
        return None
    
    def visit_binary_expression(self, expr: expression_ast.BinaryExpression):
        """Generate code for binary operation."""
        # Evaluate left operand
        expr.left.accept(self)
        self.emit("    addi sp, sp, -4")
        self.emit("    sw t0, 0(sp)  # Push left")
        
        # Evaluate right operand
        expr.right.accept(self)
        self.emit("    mv t1, t0")
        self.emit("    lw t0, 0(sp)  # Pop left")
        self.emit("    addi sp, sp, 4")
        
        # Perform operation
        op = expr.operator.value if hasattr(expr.operator, 'value') else str(expr.operator)
        
        if op == "+":
            self.emit("    add t0, t0, t1")
        elif op == "-":
            self.emit("    sub t0, t0, t1")
        elif op == "*":
            self.emit("    mul t0, t0, t1")
        elif op == "/":
            self.emit("    div t0, t0, t1")
        elif op == "<":
            self.emit("    slt t0, t0, t1")
        elif op == ">":
            self.emit("    slt t0, t1, t0")
        elif op == "<=":
            self.emit("    slt t0, t1, t0")
            self.emit("    xori t0, t0, 1")
        elif op == ">=":
            self.emit("    slt t0, t0, t1")
            self.emit("    xori t0, t0, 1")
        elif op == "==":
            self.emit("    sub t0, t0, t1")
            self.emit("    seqz t0, t0")
        elif op == "!=":
            self.emit("    sub t0, t0, t1")
            self.emit("    snez t0, t0")
        elif op == "&&":
            self.emit("    and t0, t0, t1")
            self.emit("    snez t0, t0")
        elif op == "||":
            self.emit("    or t0, t0, t1")
            self.emit("    snez t0, t0")
        
        return None
    
    def visit_unary_expression(self, expr: expression_ast.UnaryExpression):
        """Generate code for unary operation."""
        expr.operand.accept(self)
        
        op = expr.operator.value if hasattr(expr.operator, 'value') else str(expr.operator)
        
        if op == "-":
            self.emit("    neg t0, t0")
        elif op == "!":
            self.emit("    seqz t0, t0")
        
        return None
    
    def visit_dot_expression(self, expr: expression_ast.DotExpression):
        """Generate code for struct field access."""
        # Evaluate struct expression (gets pointer)
        expr.left.accept(self)
        self.emit("    mv t2, t0  # Save struct pointer")
        
        # Get field offset - need to determine struct type
        field_name = self.Name(expr.id)
        
        # Try to determine the struct type from the left expression
        struct_type_name = self._get_struct_type(expr.left)
        
        if struct_type_name and struct_type_name in self.structs:
            fields = self.structs[struct_type_name]["fields"]
            if field_name in fields:
                offset = fields[field_name]
                self.emit(f"    lw t0, {offset}(t2)  # Load field {field_name}")
            else:
                self.emit(f"    # ERROR: Field {field_name} not found in struct {struct_type_name}")
                self.emit("    li t0, 0")
        else:
            # Fallback: assume offset 0
            self.emit(f"    lw t0, 0(t2)  # Load field {field_name} (unknown struct type)")
        
        return None
    
    def _get_struct_type(self, expr):
        """Try to determine the struct type of an expression."""
        if isinstance(expr, expression_ast.IdentifierExpression):
            var_name = expr.id
            if var_name in self.type_environment:
                var_type = self.type_environment[var_name]
                if isinstance(var_type, type_ast.StructType):
                    return self.Name(var_type.name)
        elif isinstance(expr, expression_ast.DotExpression):
            # For nested dot expressions, would need more complex type tracking
            return None
        return None
    
    def visit_invocation_expression(self, expr: expression_ast.InvocationExpression):
        """Generate code for function call."""
        fname = self.Name(expr.name)
        
        # Save a0-a7 if we have complex argument expressions
        num_args = len(expr.arguments)
        args_to_save = min(num_args, 8)
        
        # Evaluate arguments in reverse order and store on stack temporarily
        temp_stack_space = num_args * 4
        if temp_stack_space > 0:
            self.emit(f"    addi sp, sp, -{temp_stack_space}")
        
        for i, arg in enumerate(expr.arguments):
            arg.accept(self)
            self.emit(f"    sw t0, {i*4}(sp)")
        
        # Move arguments from stack to registers
        for i in range(min(num_args, 8)):
            self.emit(f"    lw a{i}, {i*4}(sp)")
        
        # Clean up temp stack space
        if temp_stack_space > 0:
            self.emit(f"    addi sp, sp, {temp_stack_space}")
        
        # Call function
        self.emit(f"    jal {fname}")
        
        # Result in a0, move to t0
        self.emit("    mv t0, a0")
        
        return None
    
    def visit_new_expression(self, expr: expression_ast.NewExpression):

        sname = self.Name(expr.id)
    
    # Get struct size
        if sname in self.structs:
            size = self.structs[sname]["size"]
        else:
            size = 4
    
    # Call sbrk from berkeley_utils to allocate on heap
        self.emit(f"    li a0, {size}")
        self.emit("    jal sbrk")
        self.emit("    mv t0, a0")
    
        return None
    
    # =========== LValues ===========
    
    def visit_lvalue_id(self, lval: lvalue_ast.LValueID):
        """Load lvalue variable into t0."""
        name = self.Name(lval.id)
        
        if name in self.locals:
            offset = self.locals[name]
            self.emit(f"    lw t0, {offset}(fp)")
        elif name in self.globals:
            label = self.globals[name]
            self.emit(f"    la t1, {label}")
            self.emit(f"    lw t0, 0(t1)")
        
        return None
    
    def visit_lvalue_dot(self, lval: lvalue_ast.LValueDot):
        """Generate code for struct field lvalue."""
        # Get struct pointer
        lval.left.accept(self)
        
        # Load field
        field_name = self.Name(lval.id)
        self.emit(f"    # Access field {field_name}")
        self.emit("    lw t0, 0(t0)")
        
        return None
    
    def _generate_lvalue_address(self, lval):
        """Generate address of lvalue into t0 (for assignment)."""
        if isinstance(lval, lvalue_ast.LValueID):
            name = self.Name(lval.id)
            
            if name in self.locals:
                offset = self.locals[name]
                self.emit(f"    addi t0, fp, {offset}")
            elif name in self.globals:
                label = self.globals[name]
                self.emit(f"    la t0, {label}")
        
        elif isinstance(lval, lvalue_ast.LValueDot):
            # Get struct pointer address
            if isinstance(lval.left, lvalue_ast.LValueID):
                # Load the struct pointer value
                name = self.Name(lval.left.id)
                if name in self.locals:
                    offset = self.locals[name]
                    self.emit(f"    lw t0, {offset}(fp)  # Load struct pointer")
                elif name in self.globals:
                    label = self.globals[name]
                    self.emit(f"    la t1, {label}")
                    self.emit(f"    lw t0, 0(t1)  # Load struct pointer")
            else:
                # Nested dot expression
                self._generate_lvalue_address(lval.left)
            
            # Add field offset
            field_name = self.Name(lval.id)
            
            # Determine struct type
            if isinstance(lval.left, lvalue_ast.LValueID):
                var_name = self.Name(lval.left.id)
                if var_name in self.type_environment:
                    var_type = self.type_environment[var_name]
                    if isinstance(var_type, type_ast.StructType):
                        struct_type_name = self.Name(var_type.name)
                        if struct_type_name in self.structs:
                            fields = self.structs[struct_type_name]["fields"]
                            if field_name in fields:
                                offset = fields[field_name]
                                self.emit(f"    addi t0, t0, {offset}  # Add field offset for {field_name}")
                                return
            
            # Fallback
            self.emit(f"    # Field {field_name} address (offset unknown)")
    
    # =========== Type Nodes (return None) ===========
    
    def visit_type_declaration(self, tdecl): return None
    def visit_declaration(self, decl): return None
    def visit_int_type(self, t): return None
    def visit_bool_type(self, t): return None
    def visit_struct_type(self, t): return None
    def visit_return_type_real(self, t): return None
    def visit_return_type_void(self, t): return None