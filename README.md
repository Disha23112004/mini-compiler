Mini Compiler
A full-featured compiler for the Mini programming language that generates optimized RISC-V RV32IM assembly code. Implements complete compilation pipeline from source code to executable assembly with comprehensive error checking and robust semantic analysis.

Table of Contents
Overview
Key Features
Installation
Usage
Language Syntax
Architecture
Memory Model
Register Allocation
Calling Convention
Implementation Details
Testing
Technical Highlights
Overview
This compiler demonstrates a production-quality multi-phase architecture with clear separation of concerns. Built from scratch, it showcases proficiency in:

Compiler Design: Full pipeline implementation with multiple intermediate representations
Computer Architecture: RISC-V assembly generation and ABI compliance
Software Engineering: Modular design, comprehensive testing, and maintainable code structure
Data Structures: Symbol tables, AST design, scope management
Algorithm Design: Type checking, semantic analysis, code generation
Key Features
✅ Complete Language Support

Primitive types: int, bool
User-defined structures with pointer semantics
First-class functions with parameters and return values
Dynamic memory allocation (new, delete)
✅ Robust Analysis

Context-sensitive type checking
Lexical scoping with nested functions
Comprehensive error reporting with line numbers
Symbol table management
✅ Efficient Code Generation

RISC-V RV32IM target architecture
Stack-based calling convention
Proper frame pointer management
Heap allocation for dynamic structures
✅ Production Features

I/O operations for program interaction
Recursive function support
Control flow: conditionals and loops
Struct field access with dot notation
Installation
Prerequisites
bash
Python 3.7+
pip (Python package manager)
Quick Start
bash
# Clone the repository
git clone https://github.com/YOUR_USERNAME/mini-compiler.git
cd mini-compiler

# Install dependencies
pip install -r requirements.txt

# Compile a sample program
python mini_compiler.py tests/simple_killer.mini

# Run the generated assembly (requires RISC-V simulator)
venus simple_killer.s
Usage
Basic Compilation
bash
python mini_compiler.py program.mini
Generates program.s with RISC-V assembly code.

Advanced Options
bash
# View Abstract Syntax Tree
python mini_compiler.py program.mini --pp

# Display Symbol Tables
python mini_compiler.py program.mini --sym

# Full debugging output
python mini_compiler.py program.mini --pp --sym
Execution
bash
# Using Venus RISC-V simulator
venus program.s [input_file.txt]

# Online: https://venus.cs61c.org/
Language Syntax
Program Structure
mini
struct LinkedList {
    int data;
    struct LinkedList next;
};

int globalCounter;

fun main() int {
    int x, y, sum;
    struct LinkedList list;
    
    x = 10;
    y = 20;
    sum = add(x, y);
    
    list = new LinkedList;
    list.data = sum;
    
    println sum;
    delete list;
    return 0;
}

fun add(int a, int b) int {
    return a + b;
}
Supported Constructs
Data Types

int - 32-bit signed integers
bool - Boolean values (true, false)
struct TypeName - User-defined structures
Control Flow

if (condition) { ... } else { ... }
while (condition) { ... }
Operations

Arithmetic: +, -, *, /
Comparison: <, >, <=, >=, ==, !=
Logical: &&, ||, !
Memory Management

new StructName - Heap allocation
delete expression - Memory deallocation
I/O

read - Read integer from input
print expression - Output without newline
println expression - Output with newline
Architecture
Compilation Pipeline
Source Code (.mini)
    ↓
[Lexical Analysis] → Tokens
    ↓
[Syntactic Analysis] → Parse Tree
    ↓
[AST Construction] → Abstract Syntax Tree
    ↓
[Semantic Analysis] → Type-checked AST + Symbol Tables
    ↓
[Code Generation] → RISC-V Assembly (.s)
Phase 1: Lexical & Syntactic Analysis
Technology: ANTLR4 parser generator
Input: Source code text
Output: Concrete Syntax Tree (CST)
Validates: Syntax correctness per language grammar
Phase 2: AST Construction
Module: mini_ast_visitor.py
Input: Parse tree from ANTLR
Output: Simplified Abstract Syntax Tree
Purpose: Removes syntactic sugar, creates clean representation
Phase 3: Semantic Analysis
Module: static_semantic_ast_visitor.py
Algorithms:
Type inference and checking
Scope resolution with nested environments
Control flow validation
Output: Type-annotated AST, symbol tables
Error Detection:
Type mismatches
Undefined variables
Invalid function calls
Missing return statements
Phase 4: Code Generation
Module: code_gen_ast_visitor.py
Target: RISC-V RV32IM ISA
Techniques:
Single-pass code generation
Stack-based expression evaluation
Struct layout optimization
Output: Executable RISC-V assembly
Memory Model
Global Variables
Allocated in .data section
Unique label per variable: global_<name>
Fixed addresses for efficient access
Stack Frame Layout
┌─────────────────┐ ← Higher addresses
│  Return Address │ fp+4
├─────────────────┤
│  Saved FP       │ fp+0  ← Frame Pointer
├─────────────────┤
│  Parameter 1    │ fp-4
├─────────────────┤
│  Parameter 2    │ fp-8
├─────────────────┤
│  Local Var 1    │ fp-12
├─────────────────┤
│  Local Var 2    │ fp-16
└─────────────────┘ ← Stack Pointer (lower addresses)
Design Benefits:

Constant offsets from frame pointer
Simple address calculation
Efficient function calls
Supports recursion
Struct Layout
Sequential field placement
O(1) offset lookup via preprocessing
Heap allocation using system call
4-byte alignment for all fields
Register Allocation
Register Usage Strategy
Register	Purpose	Preservation
t0	Primary expression result	Temporary
t1	Secondary operand	Temporary
t2	Struct pointer storage	Temporary
a0-a7	Function arguments 1-8	Temporary
a0	Function return value	Temporary
fp (s0)	Frame pointer	Callee-saved
ra	Return address	Callee-saved
sp	Stack pointer	Maintained
Expression Evaluation
Stack-based approach for correctness:

Evaluate left operand → t0
Push t0 to stack
Evaluate right operand → t0
Pop stack to t1
Compute: t0 = t0 OP t1
This guarantees correct evaluation order for complex nested expressions.

Calling Convention
RISC-V ABI Compliance
Caller Responsibilities:

Evaluate and pass first 8 arguments in a0-a7
Additional arguments on stack
Save caller-saved registers if needed
Execute jal function_name
Callee Responsibilities:

asm
function:
    # Prologue
    addi sp, sp, -8
    sw ra, 4(sp)
    sw fp, 0(sp)
    addi fp, sp, 0
    
    # Allocate locals
    addi sp, sp, -N
    
    # Function body
    ...
    
    # Epilogue
    addi sp, sp, N
    lw fp, 0(sp)
    lw ra, 4(sp)
    addi sp, sp, 8
    jr ra
Implementation Details
Key Algorithms
Type Checking:

Bottom-up type inference
Context-sensitive analysis
Null pointer handling for structs
Code Generation:

Single-pass with symbol table lookup
Immediate struct layout calculation
Efficient temporary management
Optimization Opportunities:

Register allocation (currently stack-based)
Dead code elimination
Constant folding
Peephole optimization
Error Handling
Comprehensive error detection with actionable messages:

Line number reporting
Clear error descriptions
Multiple error collection (doesn't stop at first error)
Suggestions for common mistakes
Example:

ERROR. Type mismatch in assignment #15
ERROR. Undefined variable 'x' #23
ERROR. Non-void function must return value #42
Testing
Test Suite
The tests/ directory contains comprehensive test cases:

bash
# Basic functionality
python mini_compiler.py tests/simple_killer.mini

# Function calls and parameters
python mini_compiler.py tests/killer_multi_func.mini

# Global variables
python mini_compiler.py tests/killer_with_global.mini

# Complex data structures
python mini_compiler.py tests/killerBubbles.mini

# I/O operations
python mini_compiler.py tests/minimal_read.mini
Test Coverage
Category	Test File	Features Tested
Basic	simple_killer.mini	Expressions, variables, control flow
Functions	killer_multi_func.mini	Multiple functions, parameters, returns
Globals	killer_with_global.mini	Global variable access
Structs	killerBubbles.mini	Linked lists, bubble sort algorithm
I/O	minimal_read.mini	File input, print operations
Comprehensive	BenchMarkishTopics.mini	All language features
Technical Highlights
What Makes This Compiler Unique
Complete Implementation: Full compilation pipeline from source to assembly, not just a toy compiler
Production Practices:
Clean separation of concerns
Visitor pattern for extensibility
Comprehensive error handling
Well-documented design decisions
Real Target Architecture: Generates actual RISC-V assembly that runs on simulators and hardware
Robust Testing: Extensive test suite including edge cases and complex programs (circular linked lists with sorting algorithms)
Semantic Sophistication:
Lexical scoping with nested environments
Type inference for expressions
Pointer semantics for structures
Proper null handling
Challenges Overcome
RISC-V Calling Convention: Implemented proper frame pointer management and parameter passing following RISC-V ABI specifications.

Type System Design: Created flexible type system supporting both primitive types and user-defined structures with pointer semantics.

Memory Management: Implemented proper stack frame allocation and heap management for dynamic structures.

Symbol Table Design: Built efficient nested scope management with O(1) lookup for lexical scoping.

Project Structure
mini-compiler/
├── mini_compiler.py              # Main driver
├── mini_ast_visitor.py           # AST construction
├── static_semantic_ast_visitor.py # Type checking
├── code_gen_ast_visitor.py       # Assembly generation
├── pretty_print_ast_visitor.py   # AST visualization
├── Mini.g4                       # Language grammar
├── MiniLexer.py                  # Generated lexer
├── MiniParser.py                 # Generated parser
├── MiniVisitor.py                # Parser visitor interface
├── miniast/                      # AST node definitions
│   ├── mini_ast.py
│   ├── program_ast.py
│   ├── statement_ast.py
│   ├── expression_ast.py
│   ├── type_ast.py
│   └── lvalue_ast.py
├── lib/                          # Runtime library
│   ├── berkeley_utils.s
│   └── read_int.s
└── tests/                        # Test suite
    ├── simple_killer.mini
    ├── killer_multi_func.mini
    ├── killer_with_global.mini
    ├── killerBubbles.mini
    ├── minimal_read.mini
    └── BenchMarkishTopics.mini
Future Enhancements
 Register allocation optimization
 Loop optimization
 Constant folding
 Dead code elimination
 Array support
 String literals
 Type inference
 LLVM backend integration


License
This project is available for educational and portfolio purposes.

Acknowledgments
ANTLR4 for parser generation framework
RISC-V Foundation for ISA specification
Berkeley for RISC-V utility libraries
Open-source compiler design community for inspiration


