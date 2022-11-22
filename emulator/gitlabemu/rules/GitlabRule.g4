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

expr
    : VARIABLE op=(EQ | NE) STRING
    | STRING op=(EQ | NE) VARIABLE
    | VARIABLE op=(MATCH | NMATCH) REGEX
    | VARIABLE op=(MATCH | NMATCH) VARIABLE
    | VARIABLE
    | expr op=AND expr
    | expr op=OR expr
    | '(' expr ')'
    ;
