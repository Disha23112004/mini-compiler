import sys
from antlr4 import *
from MiniLexer import MiniLexer
from MiniParser import MiniParser
from mini_ast_visitor import MiniToASTVisitor
from pretty_print_ast_visitor import PPASTVisitor
from static_semantic_ast_visitor import SemanticAnalyzer
from code_gen_ast_visitor import CodeGenVisitor

def main(argv):
    if len(argv) < 2:
        print("Usage: python mini_compiler.py <input.mini> [--pp] [--sym]")
        sys.exit(1)
    
    input_file = argv[1]
    
    # Check if file exists and has .mini extension
    if not input_file.endswith('.mini'):
        print("Error: Input file must have .mini extension")
        sys.exit(1)
    
    try:
        input_stream = FileStream(input_file)
    except FileNotFoundError:
        print(f"Error: File '{input_file}' not found")
        sys.exit(1)
    
    # Lexing and Parsing
    lexer = MiniLexer(input_stream)
    stream = CommonTokenStream(lexer)
    parser = MiniParser(stream)
    program_ctx = parser.program()

    if parser.getNumberOfSyntaxErrors() > 0:
        print("Syntax errors.")
        sys.exit(1)
    
    print("Parse successful.")
    
    # Create AST
    mini_ast_visitor = MiniToASTVisitor()
    mini_ast = mini_ast_visitor.visitProgram(program_ctx)
    print("AST created.")
    
    # Pretty print AST if requested
    if "--pp" in argv:
        pp = PPASTVisitor()
        output = mini_ast.accept(pp)
        print("\nPretty-printed AST:\n")
        print(output)
    
    # Semantic Analysis
    analyzer = SemanticAnalyzer()
    errors = analyzer.analyze(mini_ast)
    
    # Exit if there are semantic errors
    if errors > 0:
        print(f"Compilation failed with {errors} error(s).")
        sys.exit(1)
    
    # Print symbol tables if requested
    if "--sym" in argv:
        analyzer.globals.print_all_scopes(analyzer)
    
    # Code Generation
    print("Generating assembly code...")
    codegen = CodeGenVisitor()
    mini_ast.accept(codegen)
    assembly_code = codegen.get_code()
    
    # Write assembly to output file
    output_filename = input_file.replace('.mini', '.s')
    try:
        with open(output_filename, 'w') as f:
            f.write(assembly_code)
        print(f"Assembly code written to {output_filename}")
        print("Compilation successful!")
    except IOError as e:
        print(f"Error writing output file: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main(sys.argv)