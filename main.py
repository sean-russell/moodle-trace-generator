import argparse
import os
import glob
import json

from parser.generic_flowchart import FlowchartCreator
from parser.generic_parser import Parser
from imagecreator.image_generator import ImageGenerator

import parser.python.parser as python_parser
import parser.python.flowchart as python_flow_parser
import imagecreator.python_generator as python_image_gen
import parser.c.parser as c_parser
import parser.c.flowchart as c_flow_parser
import imagecreator.c_generator as c_image_gen

from builder.builder import Builder
from builder.extra_tags import quiz
from typing import List, Dict
import parser.multiplier as template_generator
import constants as c


def delete_temp() -> None:
    files = glob.glob('temp/*.*')

    for file_name in files:
        try:
            os.remove(file_name)
        except OSError as e:
            print("Error: %s : %s" % (file_name, e.strerror))


def generate_templated_code_question(q_root: quiz, parser: Parser, flowchart_parser: FlowchartCreator, code_file: str, parameter_file: str, question_name: str, image_generator: ImageGenerator, generate_file_questions: bool,
                                     generate_line_questions: bool, omit_ert: bool, animate_fb: bool, display_const: bool, only_line_numbers: List[int], input_dict: Dict[str, str]):
    templated_codes = template_generator.generate_from_template(code_file, parameter_file, question_name)
    num = 0
    for name, source_code in templated_codes:
        std_in = []
        if input_dict and str(num) in input_dict:
            std_in = input_dict[str(num)].split("\n")
            parser.set_input(std_in)
        code_list, line_numbers = parser.parse_source(source_code)
        builder = Builder(parser, flowchart_parser, image_generator, omit_ert, display_const, animate_fb, code_list)
        image = image_generator.get_code_image(source_code)

        if generate_line_questions:
            questions = builder.build_line_questions(code_list, image, name, only_line_numbers, std_in)
            for q in questions:
                q_root.add(q)

        if generate_file_questions:
            explanations: List[str] = Parser.get_explanations_code(code_list)
            tags = list(set([c.get_tag(x) for x in explanations]))
            questions = builder.build_file_question(code_list, name, source_code, tags, std_in)
            for q in questions:
                q_root.add(q)
        num = num + 1


def generate_code_question(q_root: quiz, parser: Parser, flowchart_parser: FlowchartCreator, code_file: str, question_name: str, image_generator: ImageGenerator, generate_file_questions: bool, generate_line_questions: bool,
                           omit_ert: bool, animate_fb: bool, display_const: bool, only_line_numbers: List[int], input_dict: Dict[str, str]):
    source_code = open(code_file).read()
    std_in = []
    if input_dict and "0" in input_dict:
        std_in = input_dict[str("0")].split("\n")
        parser.set_input(std_in)
    code_list, line_numbers = parser.parse_source(source_code)
    builder = Builder(parser, flowchart_parser, image_generator, omit_ert, display_const, animate_fb, code_list)
    image = image_generator.get_code_image(source_code)
    if generate_line_questions:
        questions = builder.build_line_questions(code_list, image, question_name, only_line_numbers, std_in)
        for q in questions:
            q_root.add(q)
    if generate_file_questions:
        explanations: List[str] = Parser.get_explanations_code(code_list)
        tags = list(set([c.get_tag(x) for x in explanations]))
        questions = builder.build_file_question(code_list, question_name, source_code, tags, std_in)
        for q in questions:
            q_root.add(q)


if __name__ == "__main__":
    arg_parser = argparse.ArgumentParser(description='Generating code tracing quiz questions for moodle')
    arg_parser.add_argument("codefile", help="This is the Python code file you want to generate a tracing quiz for",
                            type=str)
    arg_parser.add_argument("-n", "--name", help="the base name for the question, if ignored the file name will be used",
                            type=str)
    arg_parser.add_argument("-p", "--parameter",
                            help="The name of a text file containing parameters to be inserted into the code template",
                            type=str)
    arg_parser.add_argument("-l", '--lang', default="python",
                            help="This option is for choosing the language of the code file (default is python).", type=str)
    arg_parser.add_argument("-c", "--category",
                            help="The name of the category you would like the questions stored in. Given in the a nested formate seperated by forward slashes. E.g. Tracing/basics. Defaults to Tracing/filename where filename is the name of the progarm being traced",
                            type=str)
    arg_parser.add_argument("-o", "--only",
                            help="a comma separated list of the line numbers that should be used for individual question generation",
                            type=str)
    arg_parser.add_argument("-s", "--stdin",
                            help="A file containing input for the program/programs being traced",
                            type=str)
    arg_parser.add_argument("-i", '--individual', dest='line', default=False, action='store_true',
                            help="Use this option if you want to generate individual questions for each line of code.")
    arg_parser.add_argument("-f", '--file', dest='file', default=False, action='store_true',
                            help="Use this option to generate only file type questions. (default)")
    arg_parser.add_argument("-b", '--both', dest='both', default=False, action='store_true',
                            help="Use this option if you want to generate both individual and file type questions.")
    arg_parser.add_argument("-r", '--reduced', dest='omit_ert', default=False, action='store_true',
                            help="This reduces the questions asked in each line for the file type questions, has no effect on line questions")
    arg_parser.add_argument("-a", '--animate', dest='animate', default=False, action='store_true',
                            help="This creates animated versions of the feedback displayed. This option takes longer to complete and adds greatly to the size of the generated quiz file.")
    arg_parser.add_argument("-d", '--display', dest='display', default=False, action='store_true',
                            help="This allows the literal value lines of individual line quesitons to be asked as questions instead of displayed as text in the calculation table.")
    arguments = arg_parser.parse_args()

    arg_reduced: bool = False
    arg_file_questions: bool
    arg_line_questions: bool
    arg_feedback_animations: bool = False
    arg_display_constants: bool = False
    arg_question_name: str
    arg_code_file: str
    arg_parameters_bool: bool = False
    arg_parameters_file: str = ""
    arg_line_numbers: List[int] = []
    arg_input_file: str = ""
    arg_input_dict: Dict[str, str] = {"0": ""}

    arg_code_file = arguments.codefile
    if not os.path.exists(arg_code_file):
        print("codefile must point to a readable file")
        quit()

    arg_input_file = arguments.stdin
    if arguments.stdin:
        if not os.path.exists(arg_input_file):
            print("stdin file must point to a readable file")
            quit()
        else:
            f = open(arg_input_file)
            arg_input_dict = json.load(f)

    if arguments.animate:
        arg_feedback_animations = True

    if arguments.display:
        arg_display_constants = True

    if arguments.only:
        arg_line_numbers = [int(x) for x in arguments.only.split(",")]

    image_file_name = "temp/" + arg_code_file.split("/")[-1].split(".")[0] + ".png"
    quiz_file_name = "quizzes/" + arg_code_file.split("/")[-1].split(".")[0] + ".xml"
    arg_question_name = arg_code_file.split("/")[-1].split(".")[0]
    if arguments.name:
        quiz_file_name = "quizzes/" + arguments.name + ".xml"
        arg_question_name = arguments.name

    category_name = "Program Tracing Questions"
    if arguments.category:
        category_name = arguments.category
    quiz_root = Builder.create_quiz(category_name)

    if arguments.omit_ert:
        arg_reduced = True

    if arguments.file:
        arg_file_questions = True
        arg_line_questions = False
    elif arguments.line:
        arg_file_questions = False
        arg_line_questions = True
    elif arguments.both:
        arg_file_questions = True
        arg_line_questions = True
    else:
        arg_file_questions = True
        arg_line_questions = False

    if arguments.parameter:
        arg_parameters_file = arguments.parameter
        arg_parameters_bool = True

    code_parser: Parser = None
    flow_parser: FlowchartCreator = None
    image_gen: ImageGenerator = None
    if arguments.lang:
        if arguments.lang.lower() == "python":
            code_parser = python_parser.PythonParser()
            flow_parser = python_flow_parser.PythonFlowCreator()
            image_gen = python_image_gen.PythonImageGenerator(flow_parser)

        elif arguments.lang.lower() == "c":
            code_parser = c_parser.CParser()
            flow_parser = c_flow_parser.CFlowCreator()
            image_gen = c_image_gen.CImageGenerator(flow_parser)
        else:
            raise Exception("This language has not been implemented yet")

    if arg_parameters_bool:
        generate_templated_code_question(quiz_root, code_parser, flow_parser, arg_code_file, arg_parameters_file, arg_question_name, image_gen, arg_file_questions, arg_line_questions, arg_reduced, arg_feedback_animations,
                                         arg_display_constants, arg_line_numbers, arg_input_dict)
    else:
        generate_code_question(quiz_root, code_parser, flow_parser, arg_code_file, arg_question_name, image_gen, arg_file_questions, arg_line_questions, arg_reduced, arg_feedback_animations, arg_display_constants, arg_line_numbers,
                               arg_input_dict)

    f = open(quiz_file_name, "w")
    f.write(str(quiz_root))
    f.close()
    delete_temp()
