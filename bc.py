from tgutil import inline
from telegram.ext import ChosenInlineResultHandler, InlineQueryHandler
from telegram import Update, InlineQueryResult, InputTextMessageContent, InlineQueryResultArticle

import ast
import operator as op

# supported operators
operators = {ast.Add: op.add, ast.Sub: op.sub, ast.Mult: op.mul,
             ast.Div: op.truediv, ast.Pow: op.pow, ast.BitXor: op.xor,
             ast.USub: op.neg, ast.Mod: op.mod}


def eval_expr(expr):
    """
    >>> eval_expr('2^6')
    4
    >>> eval_expr('2**6')
    64
    >>> eval_expr('1 + 2*3**(4^5) / (6 + -7)')
    -5.0
    """
    return eval_(ast.parse(expr, mode='eval').body)


def eval_(node):
    if isinstance(node, ast.Num):  # <number>
        return node.n
    elif isinstance(node, ast.BinOp):  # <left> <operator> <right>
        return operators[type(node.op)](eval_(node.left), eval_(node.right))
    elif isinstance(node, ast.UnaryOp):  # <operator> <operand> e.g., -1
        return operators[type(node.op)](eval_(node.operand))
    else:
        raise TypeError(node)

@inline('^bc\s.*')
def bc(update, _):
    query = update.inline_query.query[2:].strip()
    try:
        result = str(eval_expr(query))
        update.inline_query.answer([InlineQueryResultArticle(
            id=1,
            title=result,
            input_message_content=InputTextMessageContent(query + '=' + result))])
    except:
        pass
