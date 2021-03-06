import shlex
import base64

from typing import List, Dict, Tuple, Any

from copy import deepcopy
from dominate.tags import img, style
from xml.dom.minidom import Element, parseString, Comment
from xml.dom import getDOMImplementation
from pygments.lexers.c_cpp import CLexer
from pygments.token import Text, Operator, Keyword, Name, String, Number, Punctuation
from parser.parser_types import Edge, Calculation, Statement, empty_statement
from builder.extra_tags import CDATA
from dominate.svg import svg, text, g, tspan, defs, rect
from dominate.util import raw
from parser.generic_flowchart import FlowchartCreator
from imagecreator.image_generator import ImageGenerator


class CImageGenerator(ImageGenerator):
    def __init__(self, flow_generator: FlowchartCreator) -> None:
        super().__init__(flow_generator)

    def _get_tspan_token(self, token_type: Any , token: str) -> tspan:
        if token_type == Name and token in ("scanf", "printf"):
            return tspan(token, font_size='18px', fill=self.FUNCTION_COLOUR)
        elif token_type in (Text, Name, Operator, Punctuation):
            if token.count(' ') == len(token):
                return tspan(raw("&#160;" * len(token)), font_size='18px', fill=self.NORMAL_COLOUR)
            elif token.count('\t') == len(token):
                return tspan(raw("&#160;" * 4 * len(token)), font_size='18px', fill=self.NORMAL_COLOUR)
            else:
                return tspan(token, font_size='18px', fill=self.NORMAL_COLOUR)
        elif token_type in (String,):
            return tspan(token, font_size='18px', fill=self.STRING_COLOUR)
        elif token_type in (String.Escape,):
            return tspan(token, font_size='18px', fill=self.KEYWORD_COLOUR)
        elif token_type == Number.Integer:
            return tspan(token, font_size='18px', fill=self.NUMBER_COLOUR)
        elif token_type == Name.Function:
            return tspan(token, font_size='18px', fill=self.FUNCTION_COLOUR)
        elif token_type in (Keyword, Keyword.Type):
            return tspan(token, font_size='18px', fill=self.KEYWORD_COLOUR)
        else:
            raise Exception("token not supported {} - {}".format(token, token_type))

    def _add_code_text(self, text_group: g, source: str) -> int:
        cl = CLexer()
        code_tokens: List[Tuple[int, Any, str]] = list(cl.get_tokens_unprocessed(source))
        h = self.STARTING_HEIGHT
        line_number = 1
        new_line = True
        line = None
        
        while len(code_tokens) > 0:
            position, token_type, token = code_tokens[0]
            code_tokens = code_tokens[1:]
            if new_line:
                line = text(str(line_number), tspan(raw("&#160;" * 2)), font_size='12px', fill=self.LINE_COLOUR, x=self.LINE_NUMBER_START_DISTANCE, y=h + self.ADJUSTMENT)
                text_group.add(line)
                line_number = line_number + 1
                new_line = False

            if token_type == Text and token == '\n':
                new_line = True
                h = h + self.LINE_SEPARATION
                continue
            
            token_tspan = self._get_tspan_token(token_type, token)
            line.add(token_tspan)
            
        return h

    def get_all_animation(self, code: List[Statement], source_code: str) -> str:
        nodes, edges = self.flow.parse_source(source_code)
        flowchart_svg_string = self.dot_to_svg_string(self._generate_flowchart_dot_string(nodes, edges))
        flowchart_svg_xml = self.remove_xml_comments(parseString(flowchart_svg_string))
        flowchart_svg_tag = flowchart_svg_xml.getElementsByTagName("svg")[0]
        graph_g = flowchart_svg_xml.getElementsByTagName("g")[0]
        svg_defs_tag = flowchart_svg_xml.createElement("defs")
        svg_style_tag = flowchart_svg_xml.createElement("style")
        svg_style_tag.setAttribute("type", "text/css")
        flowchart_svg_tag.appendChild(svg_defs_tag)
        svg_defs_tag.appendChild(svg_style_tag)
        w, gr = self.generate_code_table_animation_svg_string(source_code, code)
        key = self._generate_animation_css(code, self.NODE_NORMAL_COLOUR, self.HIGHLIGHT_COLOUR)
        cdata = flowchart_svg_xml.createCDATASection(key)
        svg_style_tag.appendChild(cdata)
        code_table_svg_tag = self.remove_xml_comments(parseString(gr))
        code_table_g_tag = code_table_svg_tag.getElementsByTagName("g")[0]
        impl = getDOMImplementation()
        new_svg_document = impl.createDocument(None, "svg", None)
        for key, val in flowchart_svg_tag.attributes.items():
            if key == "width":
                flow_width = int(val[:-2])
                code_table_g_tag.setAttribute("transform", "translate({} 0) scale(2 2) rotate(0) ".format(flow_width))
                new_width = str(flow_width + w * 2) + "pt"
                new_svg_document.firstChild.setAttribute(key, new_width)
            elif key.lower() == "viewbox":
                new_view = " ".join([str(float(a) + w * 2) if i == 2 else a for i, a in enumerate(val.split(" "))])
                new_svg_document.firstChild.setAttribute(key, new_view)
            else:
                new_svg_document.firstChild.setAttribute(key, val)

        code_table_group_string = ''.join([line for line in code_table_g_tag.toprettyxml(indent='').split('\n') if line.strip()])
        ast_group_string = ''.join([line for line in graph_g.toprettyxml(indent='').split('\n') if line.strip()])
        defs_string = ''.join([line for line in svg_defs_tag.toprettyxml(indent='').split('\n') if line.strip()])
        svg_string = ''.join([line for line in new_svg_document.toprettyxml(indent='').split('\n') if line.strip()])
        pretty = self.pretty_xml(self.remove_xml_comments(parseString(svg_string[:-2] + ">" + code_table_group_string + ast_group_string + defs_string + "</svg>")))
        return pretty
        # byte_array = base64.b64encode(pretty.encode('utf8'))
        # return img(alt="", _class="img-responsive atto_image_button_text-bottom", style="object-fit:contain", width="100%", src="data:image/svg+xml;base64," + str(byte_array)[2:-1])

    def generate_code_table_animation_svg_string(self, source: str, code_list: List[Statement]) -> Tuple[float, str]:
        variables :List[str] = code_list[-1]["variables_after"].keys()
        code_list_copy: List[Statement] = [empty_statement(0)] + deepcopy(code_list) + [empty_statement(-1)]
        lines = source.splitlines()
        frames = len(lines) + 2
        exe_code_len = [len(stat["calculation"]["code"]) * (self.CHAR_WIDTH + 2) + 90 for stat in code_list_copy]
        height = frames * self.LINE_SEPARATION + self.LINE_SEPARATION * (len(variables) + 1)
        width = max( [len(line) * self.CHAR_WIDTH + self.CODE_START_DISTANCE * 2 for line in lines] + exe_code_len + [256])
        code_svg: svg = svg(id="svg", width=width, height=height, viewBox="0.00 0.00 {} {}".format(width, height), xmlns="http://www.w3.org/2000/svg")
        alt_svg = g(id="code_table")
        code_svg += alt_svg
        alt_svg += rect(fill=self.BACKGROUND_COLOUR, height=height, width=width, x=0, y=0)
        for i in range(frames):
            alt_svg += rect(fill=self.CODE_HIGHLIGHT_COLOUR, height=self.LINE_SEPARATION + 1, width=width, x=0, y=i * self.LINE_SEPARATION, visibility="hidden", opacity=0.5, _class="codeline{}".format(i))
            self.last_code_highlight = i
        animation_string = self._generate_animation_css(code_list, self.BACKGROUND_COLOUR, self.CODE_HIGHLIGHT_COLOUR)
        code_svg += defs(style(CDATA(self.STYLESHEET.format(animation_string)), type="text/css"))
        text_group = g(_class="normal")
        alt_svg += text_group
        h = self._add_code_text(text_group, source)
        table = g()
        h = h + self.LINE_SEPARATION
        table += rect(fill=self.NODE_NORMAL_COLOUR, height=self.LINE_SEPARATION * (len(variables) + 1), width=width, x=0, y=h, stroke=self.BACKGROUND_COLOUR)

        table += rect(fill=self.BACKGROUND_COLOUR, height=self.LINE_SEPARATION, width=len(" Code:    ") * self.CHAR_WIDTH, x=0, y=h, stroke=self.NODE_NORMAL_COLOUR)
        table += text("Code:", font_size='18px', fill=self.NODE_NORMAL_COLOUR, x=self.CHAR_WIDTH, y=h + self.ADJUSTMENT, _class="normal")
        table += rect(fill=self.BACKGROUND_COLOUR, height=self.LINE_SEPARATION, width=width - (len(" Code:    ") * self.CHAR_WIDTH), x=len(" Code:    ") * self.CHAR_WIDTH, y=h, stroke=self.NODE_NORMAL_COLOUR)
        for i, stat in enumerate(code_list_copy):
            text_tag = text(font_size='18px', fill=self.BACKGROUND_COLOUR, x=len(" Code:      ") * self.CHAR_WIDTH, y=h + self.ADJUSTMENT, _class="alternate code_display{}".format(i), visibility="hidden")
            cl = CLexer()
            code_tokens: List[Tuple[int, Any, str]] = list(cl.get_tokens_unprocessed(stat["calculation"]["code"]))
            while len(code_tokens) > 0:
                position, token_type, token = code_tokens[0]
                code_tokens = code_tokens[1:]
                token_tspan = self._get_tspan_token(token_type, token)
                text_tag +=token_tspan
            table += text_tag

        for i, v in enumerate(variables):
            h = h + self.LINE_SEPARATION
            table += rect(fill=self.BACKGROUND_COLOUR, height=self.LINE_SEPARATION, width=len(" Code:    ") * self.CHAR_WIDTH, x=0, y=h, stroke=self.NODE_NORMAL_COLOUR)
            table += text(v, font_size='18px', fill=self.NODE_NORMAL_COLOUR, x=self.CHAR_WIDTH, y=h + self.ADJUSTMENT, _class="normal")
            table += rect(fill=self.BACKGROUND_COLOUR, height=self.LINE_SEPARATION, width=width - (len(" Code:    ") * self.CHAR_WIDTH), x=len(" Code:    ") * self.CHAR_WIDTH, y=h, stroke=self.NODE_NORMAL_COLOUR)
            for vn, stat in enumerate(code_list_copy):
                if v in stat["variables_after"]:
                    tp, add, size = stat["variables_after"][v]
                   
                    # print(var)
                    text_tag = text(font_size='18px', fill=self.BACKGROUND_COLOUR, x=len(" Code:      ") * self.CHAR_WIDTH, y=h + self.ADJUSTMENT, _class="alternate var_display{}_{}".format(vn, i), visibility="hidden")
                    cl = CLexer()
                    code_tokens: List[Tuple[int, Any, str]] = []
                    if size == 1:
                        code_tokens = list(cl.get_tokens_unprocessed(stat["memory_after"][add]["value_show"]))
                    else:
                        values = []
                        for index in range(size):
                            values.append(stat["memory_after"][add+index]["value_show"])
                        code_tokens.extend(list(cl.get_tokens_unprocessed("{ "+", ".join(values)+" }")))
                    while len(code_tokens) > 0:
                        position, token_type, token = code_tokens[0]
                        code_tokens = code_tokens[1:]
                        token_tspan = self._get_tspan_token(token_type, token)
                        text_tag +=token_tspan
                    table += text_tag
                    # table += text(stat["memory_after"][stat["variables_after"][v][1]]["value_show"], font_size='18px', fill=self.BACKGROUND_COLOUR, x=len(" Code:   ") * self.CHAR_WIDTH, y=h + self.ADJUSTMENT,
                    #               _class="alternate var_display{}_{}".format(vn, i), visibility="hidden")
                else:
                    table += text("?", font_size='18px', fill=self.BACKGROUND_COLOUR, x=len(" Code:   ") * self.CHAR_WIDTH, y=h + self.ADJUSTMENT, _class="alternate var_display{}_{}".format(vn, i), visibility="hidden")
        alt_svg += table
        return width, code_svg.render(xhtml=True)
