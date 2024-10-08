from .OpenglAst import *
from .OpenglParser import *
from .OpenglLexer import *


class GLSLToCrossGLConverter:
    def __init__(self, shader_type="vertex"):
        self.shader_type = shader_type
        self.structures = {"VSInput": [], "PSOutput": [], "PSInput": [], "VSOutput": []}
        self.gl_position = False
        self.type_mapping = {}
        self.semantic_map = {
            "gl_VertexID": "gl_VertexID",
            "gl_InstanceID": "gl_InstanceID",
            "gl_FrontFacing": "gl_IsFrontFace",
            "gl_PrimitiveID": "gl_PrimitiveID",
            "layout(location = 8)": "TEXCOORD3",
            "layout(location = 9)": "TEXCOORD4",
            "layout(location = 10)": "TEXCOORD5",
            "layout(location = 11)": "TEXCOORD6",
            "layout(location = 12)": "TEXCOORD7",
            "gl_Position": "gl_Position",
            "gl_PointSize": "gl_PointSize",
            "gl_ClipDistance": "gl_ClipDistance",
            "layout(location = 0)": "gl_FragColor",
            "layout(location = 1)": "gl_FragColor1",
            "layout(location = 2)": "gl_FragColor2",
            "layout(location = 3)": "gl_FragColor3",
            "layout(location = 4)": "gl_FragColor4",
            "layout(location = 5)": "gl_FragColor5",
            "layout(location = 6)": "gl_FragColor6",
            "layout(location = 7)": "gl_FragColor7",
            "gl_FragDepth": "gl_FragDepth",
            "gl_FragCoord": "gl_FragCoord",
            "gl_PointCoord": "gl_PointCoord",
            "gl_GlobalInvocationID": "gl_GlobalInvocationID",
            "gl_LocalInvocationID": "gl_LocalInvocationID",
            "gl_WorkGroupID": "gl_WorkGroupID",
            "gl_LocalInvocationIndex": "gl_LocalInvocationIndex",
            "gl_WorkGroupSize": "gl_WorkGroupSize",
            "gl_NumWorkGroups": "gl_NumWorkGroups",
        }

    def generate(self, ast):
        self.gl_position = False
        code = "shader main {\n"
        # Generate custom functions
        code += " \n"
        self.check_for_gl_position(ast)
        if self.gl_position:
            self.structures["VSOutput"].append(("vec4", "position", None))
        for uniform in ast.uniforms:
            code += f"    cbuffer uniforms {{\n"
            if isinstance(uniform, UniformNode):
                code += f"        {uniform.vtype} {uniform.name};\n"
            code += "    }\n\n"

        for var in ast.io_variables:
            if isinstance(var, LayoutNode):
                if var.io_type == "vertex_IN":
                    self.structures["VSInput"].append(
                        (var.dtype, var.name, var.semantic)
                    )
                elif var.io_type == "vertex_OUT":
                    self.structures["VSOutput"].append(
                        (var.dtype, var.name, var.semantic)
                    )
                elif var.io_type == "fragment_IN":
                    self.structures["PSInput"].append(
                        (var.dtype, var.name, var.semantic)
                    )
                elif var.io_type == "fragment_OUT":
                    self.structures["PSOutput"].append(
                        (var.dtype, var.name, var.semantic)
                    )
            elif isinstance(var, VariableNode):
                if var.io_type == "vertex_IN":
                    self.structures["VSInput"].append(
                        (var.vtype, var.name, var.semantic)
                    )
                elif var.io_type == "vertex_OUT":
                    self.structures["VSOutput"].append(
                        (var.vtype, var.name, var.semantic)
                    )
                elif var.io_type == "fragment_IN":
                    self.structures["PSInput"].append(
                        (var.vtype, var.name, var.semantic)
                    )
                elif var.io_type == "fragment_OUT":
                    self.structures["PSOutput"].append(
                        (var.vtype, var.name, var.semantic)
                    )
            else:
                raise ValueError("Invalid io type")
        for struct_name, members in self.structures.items():
            if members:
                code += f"struct {struct_name} {{\n"
                for i, (dtype, name, semantic) in enumerate(members):
                    if struct_name == "VSInput":
                        code += f"    {dtype} {name} {self.map_semantic(semantic,i)};\n"
                    elif struct_name == "VSOutput":
                        code += f"    {dtype} {name} {self.map_semantic(semantic,i)};\n"
                    elif struct_name == "PSInput":
                        code += f"    {dtype} {name} {self.map_semantic(semantic,i)};\n"
                    elif struct_name == "PSOutput":
                        code += f"    {dtype} {name} {self.map_semantic(semantic,i)};\n"
                code += "};\n\n"

        for constant in ast.constant:
            code += f"    static {constant.vtype} {constant.name} = {constant.value};\n"
        code += " \n"

        for global_variable in ast.global_variables:
            code += f"    {global_variable.vtype} {global_variable.name};\n"
        for f in ast.functions:
            code += self.generate_functions(f)
        code += "}\n"
        return code

    def check_for_gl_position(self, ast):
        for f in ast.functions:
            if f.name == "main":
                for stmt in f.body:
                    if isinstance(stmt, BinaryOpNode):
                        if isinstance(stmt.left, str) and stmt.left == "gl_Position":
                            self.gl_position = True
                        elif (
                            isinstance(stmt.left, VariableNode)
                            and stmt.left.name == "gl_Position"
                        ):
                            self.gl_position = True

    def generate_functions(self, functions):
        code = ""
        if functions.qualifier == "vertex":
            code += "vertex {\n"
            code += "      VSOutput main(VSInput input) {\n"
            code += "         VSOutput output;\n"
        elif functions.qualifier == "fragment":
            code += "fragment {\n"
            code += "       PSOutput main(PSInput input) {\n"
            code += "        PSOutput output;\n"
        else:
            params = ", ".join(
                f"{self.map_type(param[0])} {param[1]}" for param in functions.params
            )
            return_type = self.map_type(functions.return_type)
            code += f"{return_type} {functions.name}({params}) {{\n"
        for stmt in functions.body:
            code += self.generate_statement(stmt, 2)
        if functions.name == "main":
            code += "        return output;\n"
            code += "        }\n"
            code += "    }\n"
        else:
            code += "        }\n\n"

        return code

    def generate_statement(self, stmt, indent=0, shader_type=None):
        indent_str = "    " * indent
        if isinstance(stmt, VariableNode):
            return f"{indent_str}{self.map_type(stmt.vtype)} {stmt.name};\n"
        elif isinstance(stmt, AssignmentNode):
            return f"{indent_str}{self.generate_assignment(stmt, shader_type)};\n"
        elif isinstance(stmt, IfNode):
            return self.generate_if(stmt, indent, shader_type)
        elif isinstance(stmt, ForNode):
            return self.generate_for(stmt, indent, shader_type)
        elif isinstance(stmt, ReturnNode):
            code = ""
            for i, return_stmt in enumerate(stmt.value):
                code += f"{self.generate_expression(return_stmt, shader_type)}"
                if i < len(stmt.value) - 1:
                    code += ", "
            return f"{indent_str}return {code};\n"
        else:
            return f"{indent_str}{self.generate_expression(stmt, shader_type)};\n"

    def generate_assignment(self, node, shader_type=None):
        if shader_type in ["vertex", "fragment"] and isinstance(node.name, str):
            if (
                node.name in self.structures["VSOutput"]
                or node.name in self.structures["PSOutput"]
            ):
                return f"output.{node.name} = {self.generate_expression(node.value, shader_type)}"
        if isinstance(node.name, VariableNode) and node.name.vtype:
            return f"{self.map_type(node.name.vtype)} {node.name.name} = {self.generate_expression(node.value, shader_type)}"
        else:
            lhs = self.generate_expression(node.name, shader_type)
            if lhs == "gl_Position" or lhs == "gl_position":
                return f"output.position = {self.generate_expression(node.value, shader_type)}"
            return f"{lhs} = {self.generate_expression(node.value, shader_type)}"

    def generate_if(self, node, indent, shader_type=None):
        indent_str = "    " * indent
        code = f"{indent_str}if ({self.generate_expression(node.if_condition, shader_type)}) {{\n"
        for stmt in node.if_body:
            code += self.generate_statement(stmt, indent + 1, shader_type)
        code += f"{indent_str}}}"

        for else_if_condition, else_if_body in zip(
            node.else_if_conditions, node.else_if_bodies
        ):
            code += f" else if ({self.generate_expression(else_if_condition, shader_type)}) {{\n"
            for stmt in else_if_body:
                code += self.generate_statement(stmt, indent + 1, shader_type)
            code += f"{indent_str}}}"

        if node.else_body:
            code += " else {\n"
            for stmt in node.else_body:
                code += self.generate_statement(stmt, indent + 1, shader_type)
            code += f"{indent_str}}}"
        code += "\n"
        return code

    def generate_for(self, node, indent, shader_type=None):
        indent_str = "    " * indent

        init = self.generate_statement(node.init, 0, shader_type).strip()[
            :-1
        ]  # Remove trailing semicolon

        condition = self.generate_statement(node.condition, 0, shader_type).strip()[
            :-1
        ]  # Remove trailing semicolon

        update = self.generate_statement(node.update, 0, shader_type).strip()[:-1]

        code = f"{indent_str}for ({init}; {condition}; {update}) {{\n"
        for stmt in node.body:
            code += self.generate_statement(stmt, indent + 1, shader_type)
        code += f"{indent_str}}}\n"
        return code

    def generate_expression(self, expr, shader_type=None):
        if isinstance(expr, str):
            return self.translate_expression(expr, shader_type)
        elif isinstance(expr, VariableNode):
            if isinstance(expr.name, str):
                return f"{self.map_type(expr.vtype)} {self.translate_expression(expr.name, shader_type)}"
            else:
                return f"{self.map_type(expr.vtype)} {self.generate_expression(expr.name, shader_type)}"
        elif isinstance(expr, BinaryOpNode):
            return f"{self.generate_expression(expr.left, shader_type)} {self.map_operator(expr.op)} {self.generate_expression(expr.right, shader_type)}"
        elif isinstance(expr, FunctionCallNode):
            args = ", ".join(
                self.generate_expression(arg, shader_type) for arg in expr.args
            )
            if expr.name in self.type_mapping.keys():
                return f"{self.map_type(expr.name)}({args})"
            else:
                func_name = self.translate_expression(expr.name, shader_type)
                return f"{func_name}({args})"
        elif isinstance(expr, UnaryOpNode):
            return f"{self.map_operator(expr.op)} {self.generate_expression(expr.operand, shader_type)}"
        elif isinstance(expr, TernaryOpNode):
            return f"{self.generate_expression(expr.condition, shader_type)} ? {self.generate_expression(expr.true_expr, shader_type)} : {self.generate_expression(expr.false_expr, shader_type)}"
        elif isinstance(expr, MemberAccessNode):
            return f"{self.generate_expression(expr.object, shader_type)}.{expr.member}"
        else:
            return str(expr)

    def translate_expression(self, expr, shader_type):
        if shader_type == "vertex":
            if expr == "gl_Position":
                return "output.position"
            for vsinput in self.structures["VSInput"]:
                if vsinput[1] == expr:
                    return f"input.{expr}"
            for vsoutput in self.structures["VSOutput"]:
                if vsoutput[1] == expr:
                    return f"output.{expr}"
        elif shader_type == "fragment":
            for psinput in self.structures["PSInput"]:
                if psinput[1] == expr:
                    return f"input.{expr}"
            for psoutput in self.structures["PSOutput"]:
                if psoutput[1] == expr:
                    return f"output.{expr}"
        return self.type_mapping.get(expr, expr)

    def map_type(self, vtype):
        if vtype == "":
            return ""
        else:
            return self.type_mapping.get(vtype, vtype)

    def map_operator(self, op):
        op_map = {
            "PLUS": "+",
            "MINUS": "-",
            "MULTIPLY": "*",
            "DIVIDE": "/",
            "BITWISE_XOR": "^",
            "LESS_THAN": "<",
            "GREATER_THAN": ">",
            "ASSIGN_ADD": "+=",
            "ASSIGN_SUB": "-=",
            "ASSIGN_OR": "|=",
            "ASSIGN_MUL": "*=",
            "ASSIGN_DIV": "/=",
            "ASSIGN_MOD": "%=",
            "ASSIGN_XOR": "^=",
            "LESS_EQUAL": "<=",
            "GREATER_EQUAL": ">=",
            "EQUAL": "==",
            "NOT_EQUAL": "!=",
            "AND": "&&",
            "OR": "||",
            "EQUALS": "=",
            "ASSIGN_SHIFT_LEFT": "<<=",
            "BITWISE_SHIFT_RIGHT": ">>",
            "BITWISE_SHIFT_LEFT": "<<",
        }
        return op_map.get(op, op)

    def map_semantic(self, semantic, i):
        if semantic is not None:
            return f"@ {self.semantic_map.get(semantic, semantic)}"
        else:
            return f"@ TEXCOORD{i}"
