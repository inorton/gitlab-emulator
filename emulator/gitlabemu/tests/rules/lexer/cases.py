# stolen from https://gitlab.com/gitlab-org/gitlab/-/blob/master/spec/lib/gitlab/ci/pipeline/expression/lexer_spec.rb

JOINED_EXPRESSIONS = {
    '$PRESENT_VARIABLE =~ /my var/ && $EMPTY_VARIABLE =~ /nope/': [
        '$PRESENT_VARIABLE', '=~', '/my var/', '&&', '$EMPTY_VARIABLE', '=~', '/nope/'],
    '$EMPTY_VARIABLE == "" && $PRESENT_VARIABLE': [
        '$EMPTY_VARIABLE', '==', '""', '&&', '$PRESENT_VARIABLE'],
    '$EMPTY_VARIABLE == "" && $PRESENT_VARIABLE != "nope"': [
        '$EMPTY_VARIABLE', '==', '""', '&&', '$PRESENT_VARIABLE', '!=', '"nope"'],
    '$PRESENT_VARIABLE && $EMPTY_VARIABLE': [
        '$PRESENT_VARIABLE', '&&', '$EMPTY_VARIABLE'],
    '$PRESENT_VARIABLE =~ /my var/ || $EMPTY_VARIABLE =~ /nope/': [
        '$PRESENT_VARIABLE', '=~', '/my var/', '||', '$EMPTY_VARIABLE', '=~', '/nope/'],
    '$EMPTY_VARIABLE == "" || $PRESENT_VARIABLE': [
        '$EMPTY_VARIABLE', '==', '""', '||', '$PRESENT_VARIABLE'],
    '$EMPTY_VARIABLE == "" || $PRESENT_VARIABLE != "nope"': [
        '$EMPTY_VARIABLE', '==', '""', '||', '$PRESENT_VARIABLE', '!=', '"nope"'],
    '$PRESENT_VARIABLE || $EMPTY_VARIABLE': [
        '$PRESENT_VARIABLE', '||', '$EMPTY_VARIABLE'],
    '$PRESENT_VARIABLE && null || $EMPTY_VARIABLE == ""': [
        '$PRESENT_VARIABLE', '&&', 'null', '||', '$EMPTY_VARIABLE', '==', '""'],
}

PARENS_EXPRESSIONS = {
    '($PRESENT_VARIABLE =~ /my var/) && $EMPTY_VARIABLE =~ /nope/': [
        '(', '$PRESENT_VARIABLE', '=~', '/my var/', ')', '&&', '$EMPTY_VARIABLE', '=~', '/nope/'],
    '$PRESENT_VARIABLE =~ /my var/ || ($EMPTY_VARIABLE =~ /nope/)': [
        '$PRESENT_VARIABLE', '=~', '/my var/', '||', '(', '$EMPTY_VARIABLE', '=~', '/nope/', ')'],
    '($PRESENT_VARIABLE && (null || $EMPTY_VARIABLE == ""))': [
        '(', '$PRESENT_VARIABLE', '&&', '(', 'null', '||', '$EMPTY_VARIABLE', '==', '""', ')', ')'],
}