"""Estados de uma ficha de produto (contrato §4) e regras de decisão humana."""

RECEBIDO = "recebido"
INCOMPLETO = "incompleto"
EXPIRADO = "expirado"
PENDENTE_REVISAO = "pendente_revisao"
APROVADO_RASCUNHO = "aprovado_para_rascunho"
APROVADO_PUBLICACAO = "aprovado_para_publicacao"
REJEITADO = "rejeitado"
INVALIDADO = "invalidado"
CANDIDATO_NAO_VERIFICADO = "candidato_nao_verificado"   # contrato 1.1 (fonte B); inexistente no modo 1.0

TODOS = (RECEBIDO, INCOMPLETO, EXPIRADO, PENDENTE_REVISAO, APROVADO_RASCUNHO,
         APROVADO_PUBLICACAO, REJEITADO, INVALIDADO)

# Únicas decisões que uma pessoa pode registrar no arquivo de decisões.
DECISOES_HUMANAS = (APROVADO_RASCUNHO, APROVADO_PUBLICACAO, REJEITADO)
APROVACOES = (APROVADO_RASCUNHO, APROVADO_PUBLICACAO)

# Estados dos quais uma ficha pode virar fragmento de rascunho de Reel.
USAVEL_EM_RASCUNHO = (APROVADO_RASCUNHO, APROVADO_PUBLICACAO)

# Contrato 1.1 (aditivo): TODOS acima continua sendo o conjunto do modo 1.0.
TODOS_V11 = TODOS + (CANDIDATO_NAO_VERIFICADO,)
