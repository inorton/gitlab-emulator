/*
 * Antlr4 grammar for gitlab rules
 * TODO does not cope with escaped quotes in strings or escaped / in regexes
 */
grammar GitlabRule;

OR: '||';
AND: '&&';
EQ: '==';
NE: '!=';
MATCH: '=~';
NMATCH: '!~';
OPAR: '(';
CPAR: ')';

expr
    : '(' expr ')'                             # parens
    |VARIABLE                                  # variable
    | REGEX                                    # regex
    | VARIABLE op=(EQ | NE) STRING             # compare
    | STRING op=(EQ | NE) VARIABLE             # compare
    | VARIABLE op=(MATCH | NMATCH) REGEX       # match
    | VARIABLE op=(MATCH | NMATCH) VARIABLE    # match
    | expr op=AND expr                         # boolAnd
    | expr op=OR expr                          # boolOr
    ;


STRING
 : '"' ~(["])*  '"'
 ;

REGEX
 : '/' ~([/])* '/'
 ;

VARIABLE
 : '$' ([0-9a-zA-Z_])+
 ;

WHITESPACE
 : [\t\r\n ]+ -> skip ;