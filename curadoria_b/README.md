# curadoria_b — curadoria manual B (Etapa 5.14-B1)

Transforma uma **ficha humana** de curadoria numa exportação do tipo B do contrato 1.1 (`curadoria_manual`), pronta para o receptor
`produtos/` (`--contrato 1.1`). **Somente dados fictícios.** Sem rede, sem preço, sem afiliado, sem publicação.

```bash
python3 -m curadoria_b curadoria_b/exemplos_ficticios/ficha_valida.json --saida /tmp/lote --agora 2026-11-17T15:00:00Z
```

Gera `SAIDA/B/produto_CURADORIA_<id>_<AAAAMMDDTHHMMSSZ>.json` e `SAIDA/B/manifest.json` (estrito: `manifestVersion`, `generatedAt`, `count`,
`files[{name, sha256, bytes}]`). O lote é preparado em `.staging_*`, validado com o receptor 1.1 e só então publicado; falha → nada em `B/`.
Uma `B/` existente nunca é sobrescrita. `--export-id` fixa o UUID (reexportação determinística); sem ele, é aleatório.

## Ficha de entrada (`fichaCuradoriaVersion = "1.0"`)
`id`, `title`, `store`, `category` (opcional), `officialUrl`, `fatos[{text, sourceRef, verifiedAt}]` (1 a 20), `referencias[{label, url}]` (até 20).
Campos de preço, disponibilidade, estoque, frete, desconto ou afiliado são **recusados**; campos desconhecidos também.

## Regras
- Exportação: `source.kind = curadoria_manual`, `system = SuzukiOfertas-Instagram-Curadoria`, `provider = CURADORIA`, preço nulo (`verification: desconhecida`),
  `availability = unknown`, `publication.state = nao_publicada`, `agentPublicationEligible = false`, `blockReason = curadoria_manual_sem_verificacao_comercial`.
- Título de risco ALTA e alegações comerciais em título ou fato são recusados (`produtos/curadoria_regras_v11.py`); encurtadores e origens não verificáveis também (por nome, sem rede).
- **`PRODUTOS_REAIS_HABILITADO = False`**: só domínios reservados para teste (`.example`, `.invalid`, `.test`, `example.com/.net/.org`) em `officialUrl`, `sourceRef` e `referencias[].url`.
  O bloqueio de dados reais do receptor (`DADOS_REAIS_HABILITADO = False`) continua. Nenhum dos dois pode ser alterado nesta etapa.
- Uma URL HTTPS válida **não** prova que o conteúdo é verdadeiro; a revisão humana continua obrigatória. A curadoria nunca autoriza publicação nem agendamento.

Testes: `python3 -m unittest discover -s curadoria_b/tests -t .`
