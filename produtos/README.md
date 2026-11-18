# Integração de produtos (Etapa 5.8) — leitor, validador e fichas

Camada do projeto Instagram que **lê a pasta de troca**, **valida o contrato JSON v1**, **deduplica e expira**
produtos e **gera fichas** com estados de aprovação, preparando a integração futura com o gerador de Reels e de
carrosséis. Implementa só o lado Instagram do contrato `CONTRATO_PRODUTOS_INSTAGRAM.md` (v1, *proposto*;
repositório privado de documentação, `docs/operacao/contratos/`).

> **Somente dados fictícios.** Nada aqui acessa rede, o agente de ofertas, bancos, cofres ou credenciais;
> nada publica, agenda ou usa a Metricool. Python padrão apenas (as dependências do gerador não são usadas).

## Uso

```bash
python3 -m produtos \
  --troca produtos/exemplos_ficticios/troca \
  --decisoes produtos/exemplos_ficticios/decisoes/decisoes_exemplo.json \
  --saida produtos/saida \
  --agora 2026-11-17T15:00:00Z
```

- `--troca`: pasta de troca, **somente leitura** (nunca é alterada; a saída não pode ficar dentro dela).
- `--decisoes`: arquivo de decisões humanas (somente leitura; ver abaixo). Sem ele, nenhuma ficha é aprovada.
- `--agora`: relógio fixo (testes/reprodução). Sem ele, usa o UTC do sistema.
- `--revalidacao-horas` (padrão **24**) e `--arquivo-dias` (padrão **30**): parâmetros do contrato, ajustáveis.
  A revalidação de 24 h é uma *proposta do contrato*, não uma regra do agente.
- Saída (`produtos/saida/`, ignorada pelo git): `fichas/<PROVEDOR>__<ID>.json|.md`, `historico.json`,
  `rejeitados.json`, `arquivados.json`, `resumo.json`.

Testes: `python3 -m unittest discover -s produtos/tests -t .` (offline; rede bloqueada em todos os testes).

## Módulos

| Módulo | Papel |
|---|---|
| `esquema.py` | Validador rigoroso (lista de permissão de campos; A × B; URLs; datas; segredos). |
| `schema/produto.v1.schema.json` | JSON Schema versionado (`1.0.0`) + `schema/CAMPOS.md` (campos). |
| `leitor.py` | Lê a pasta de troca: ignora `.tmp`/ocultos/não-JSON/links; `manifest.json` opcional; quarentena. |
| `registro.py` | Deduplicação (`provider + product.id`), histórico, arquivamento por idade. |
| `avaliacao.py` | Expiração e estados; aplica decisões humanas. |
| `decisoes.py` | **Lê** o arquivo de decisões humanas (nunca grava). |
| `fotos.py` | Registro de permissão de foto (só metadados; nada é baixado). |
| `fichas.py` | Ficha JSON + Markdown a partir do dado já validado. |
| `reel_fragmento.py` | Ficha aprovada → fragmento de configuração do gerador de Reels (**não executa o gerador**). |
| `pipeline.py`, `__main__.py` | Orquestração e CLI. |

## Regras principais

**Rejeição.** JSON inválido/truncado, campo obrigatório ausente, tipo errado, preço não inteiro ou ≤ 0, moeda ≠
BRL, URL não HTTPS ou com credenciais/porta/IP/`localhost`/parâmetro de sessão ou token (e de rastreio em
`officialUrl`), datas inválidas ou futuras, `validUntil` ≤ `verifiedAt`, valores com aparência de segredo,
caracteres de controle/invisíveis. **Qualquer campo fora da lista de permissão rejeita o arquivo inteiro** (nada é
copiado). As mensagens citam o *caminho* do campo, nunca o valor.

**Destinos.** `rejeitado` (inválido), `quarentena` (JSON truncado/inválido, chaves duplicadas, hash divergente do
manifesto, arquivo não listado, `schemaVersion` de major desconhecida, arquivo grande demais) e `ignorado`
(`.json` sem `schemaVersion`/`exportId`, conforme contrato §7). Arquivos só por faltarem campos obrigatórios saem
no relatório como `dados_insuficientes`, com a lista dos campos faltantes. O relatório (`rejeitados.json`) é a
"cópia do relatório": o arquivo original **nunca** é movido, alterado ou apagado.

**Fonte A × B.**
- A (`agente_publicada`): exige `verifiedAt`/`validUntil`, `verification = ao_vivo`, `publication.state =
  publicada` + `publishedAt`, `affiliateUrl`, `photo.usePermission`.
- B (`catalogo_candidato`/`api_candidato`): `state = nao_publicada`, `agentPublicationEligible = false`, sem
  `affiliateUrl`, sem `publishedAt`, sem `ao_vivo`. B **nunca** pode se declarar publicada, elegível ou verificada.

**Deduplicação.** Chave `provider + product.id`; vale o `exportedAt` mais recente (empate: maior `exportId`).
Versões antigas ficam no `historico.json` (nada é descartado em silêncio). Exportações com mais de 30 dias são
*arquivadas* (listadas, nunca reutilizadas automaticamente).

**Expiração (estado automático, em ordem).** B → `expirado` (sem verificação). A → `expirado` se
`agora > validUntil` (limite inclusivo) ou se `agora − verifiedAt > revalidação (24 h)`; indisponível →
`invalidado`; sem foto autorizada → `incompleto`; caso contrário `pendente_revisao`.

**Foto.** Só é utilizável com `usePermission = confirmada` (que exige URL, `permissionRef` e `checkedAt`). Padrão:
`pendente`. Nenhuma imagem é baixada; foto de IA nunca representa produto específico.

**Estados e decisões humanas.** `aprovado_*` só nasce de uma decisão registrada à mão em `decisoes.json`
(`provider`, `productId`, `exportId` da versão revisada, `decisao`, `autor`, `data`, `motivo`). Nenhuma automação
aprova. A decisão vale enquanto o preço não mudar; mudança de preço volta a ficha para `pendente_revisao`.
Decisões inválidas (autor com nome de automação, data futura/anterior à exportação, `exportId` desconhecido…) são
ignoradas e relatadas. `aprovado_para_publicacao` apenas registra a autorização — **publicar/agendar exige
autorização própria, fora deste fluxo**; B nunca chega a esse estado.

## Gerador de Reels (sem integração)

`reel_fragmento.ficha_para_fragmento(ficha, foto_local)` gera `{"scenes": [cena]}` no formato real do gerador
(`reels/reel_gen/config.py`: `source.kind = real_photo`, `camera`, `transition_out`…). `validar_fragmento()` confere
o fragmento contra o esquema real e a política de conteúdo (`normalize` + `check_rules`) **sem** executar o gerador
e sem alterá-lo. O preço fica **fora do vídeo** (nunca preenche `price/discount/stock/rating`); a ficha traz o aviso
para a legenda. Divergências em relação ao plano estão em `schema/CAMPOS.md` (seção "Decisões e divergências").

---

## Modo 1.1 (contrato v1.1 — Etapa 5.11)

> **Especificação aprovada; implementação testada SOMENTE com dados fictícios e offline. Não validada em serviço real, nenhuma
> aprovação para produção.** O modo 1.0 acima permanece o padrão e **não mudou**: a saída é idêntica byte a byte (hashes golden
> do commit `b317f17` em `tests/golden/golden_modo_1_0.json`, conferidos por `tests/test_golden_modo_1_0.py`).

Adoção **explícita** (`--contrato 1.1`; biblioteca: `pipeline_v11.processar_v11` + `ConfiguracaoV11`). Sem `--contrato`, nada muda.

```bash
python3 -m produtos --contrato 1.1 --dados produtos/exemplos_ficticios_v1_1/exportacoes \
  --decisoes produtos/exemplos_ficticios_v1_1/decisoes/decisoes.json \
  --permissoes produtos/exemplos_ficticios_v1_1/decisoes/permissoes_fotos.json \
  --termos produtos/exemplos_ficticios_v1_1/decisoes/termos_programas.json \
  --fotos-dir produtos/exemplos_ficticios_v1_1/fotos --saida /tmp/saida_v11 --agora 2026-11-17T15:00:00Z
```

| Módulo novo | Papel (contrato) |
|---|---|
| `leitor_v11.py` | **`manifest.json` obrigatório em cada pasta `A/` e `B/`** (lotes independentes, sem recursão). Sem manifesto, ilegível, contagem/lista/hash inconsistentes ou arquivo não listado → **lote inteiro em quarentena**. Fonte na pasta errada → quarentena do arquivo. (§2/S4) |
| `avaliacao_v11.py` | Teto de 24 h **que não pode ser desativado nem aumentado**; B → `candidato_nao_verificado` (só rascunho editorial); identidade/preço invalidam aprovação; fatos frescos × em revisão (30 dias; dormente sem fonte de fatos). (§4, §5, §7.2, §9) |
| `permissoes.py` | Lê `termos_programas.json` e `permissoes_fotos.json` (nunca grava). Foto só com registro humano + termo + hash do arquivo (≤ 2 MB, JPEG/PNG/WebP). `photo.usePermission` exportado é **informativo**. (§8, §10) |
| `prepublicacao.py` | Portão puro `liberar / omitir_alegacao / bloquear` com relógio e horário efetivo como parâmetros. (§6) |
| `politica_titulos.py` | Níveis ALTA/MÉDIA (lista mínima, sujeita a falsos positivos). (§7.1) |
| `fichas_v11.py`, `pipeline_v11.py`, `reel_fragmento_v11.py` | Ficha 1.1, orquestração (saída nunca dentro de uma entrada; S2) e fragmento com conferência de hash (§8.8). |

**Desabilitado / inexistente (sem simulação):** reverificação do preço no instante da publicação (§6.3); verificação de autoria de commit
(S3 → `nao_verificavel` no `resumo.json`); importador de fotos; exportador do agente; qualquer publicação/agendamento. O portão
apenas **recomenda**. O `resumo.json` registra o contrato aplicado, o estado de cada lote e os commits informados (`--commit-dados`, `--commit-decisoes`, `--commit-fotos`).

Exemplos fictícios do 1.1: `exemplos_ficticios_v1_1/` (imagem sintética de ruído; nenhum dado real).

### Etapa 5.12 — correções do receptor 1.1 (P-01 a P-04)

Ainda **somente dados fictícios**; modo 1.0 intacto (hashes golden idênticos).

| Item | O que mudou (modo 1.1 apenas) |
|---|---|
| P-01 | `manifesto_v11.py`: manifesto **estrito** — `manifestVersion` (1.x), `generatedAt` (UTC, não futuro), `count`, `files[{name, sha256, bytes}]`; nenhum campo desconhecido; nomes simples e únicos; até 1000 itens; `bytes` ≤ 256 KiB. `leitor_v11` confere também `count` × arquivos presentes, `sha256` e `bytes`. Qualquer falha → **lote inteiro em quarentena**, sem tocar nos arquivos. |
| P-02 | `selecao_contrato.py` + `--dados-reais`/`--legado`: com `--dados-reais`, `--contrato` é obrigatório (sem padrão) e `1.0` exige `--legado`. O processamento de dados reais continua **desabilitado** (`DADOS_REAIS_HABILITADO = False`; o CLI sai com código 3 sem ler nada). Sem `--dados-reais` o CLI 1.0 é exatamente o de antes. |
| P-03 | `conflitos_v11.py`: A só prevalece no comercial com verificação válida; A expirada → ficha sustentada por B (`candidato_nao_verificado`, sem alegação comercial) com `fonteComercial` visível; B fornece dados editoriais (`editorialB`); divergência de título/loja/URL/características → `pendente_revisao` com os campos (`divergenciasAB`); nenhuma fonte substitui decisão humana ou permissão de foto. |
| P-04 | Toda decisão humana não aplicada entra em `decisoesInaplicaveis` (ficha, avisos e `resumo.json`) com código e motivo; decisões sobre produto ausente das fontes lidas aparecem em `decisoesSemProduto`. Nada é aprovado automaticamente. |

Não há campo de "modelo" no formato exportado: a comparação A × B usa título, loja, URL oficial e conjunto de `verifiedFacts`.

### Etapa 5.14-A (commit 1) — P-08: invalidação seletiva de aprovações

`impressao_v11.py`: uma aprovação humana **não** é invalidada por nova exportação sem alteração material. Compara-se a versão revisada
(a do `exportId` da decisão) com a vigente da mesma fonte, por tipo de decisão: rascunho = identidade, fonte, fatos, fonte de comprovação;
publicação = isso + preço (`amountCents`, `currency`, `originalAmountCents`) e disponibilidade. A divergência A × B só invalida se surgir campo
novo divergente. Ficam fora: `exportId`, `exportedAt`, `verifiedAt`, `validUntil`, `checkedAt`. Códigos em `decisoesInaplicaveis`: `identidade_mudou`,
`fonte_mudou`, `fatos_mudaram`, `fonte_comprovacao_mudou`, `preco_mudou`, `disponibilidade_mudou`, `divergencia_ab_alterada` (com `codigos` e
`campos`). `decisoes.json` não muda; a impressão é recalculada na leitura (versão revisada ausente → `versao_desconhecida`, conservador e registrado).
Aprovação editorial **não** é validade comercial: a janela de 24 h e o portão de pré-publicação seguem valendo.

### Etapa 5.14-A (commit 2) — ponte ficha 1.1 → carrossel

`carrossel_fragmento_v11.ficha_para_carrossel_v11(ficha, *, t_publicacao, foto_catalogo_id, recurso_visual, catalogo, links_oficiais, alegacoes,
preco_aprovado_centavos, ...)`: função pura (sem rede, sem relógio, sem gravação) que devolve o JSON no formato de `exemplos/carrossel_exemplo.json`
(`id`, `permitir_fotos_pendentes`, `slides[]` com `layout`, `foto`, `foco`, `titulo`, `destaque`, `texto`) mais `bloqueios`, `avisos` e `alegacoes_omitidas`.
O resultado é sempre rascunho (`aprovado_para_publicacao` nunca é definido). Fonte B: só editorial, sem preço/desconto/estoque/urgência. Fonte A: alegações
comerciais só se o portão (`prepublicacao`) permitir para `t_publicacao`; essencial inválida bloqueia, acessória inválida é omitida e registrada. Título ALTA bloqueia;
MÉDIA exige revisão. Foto real só com permissão humana + hash do catálogo igual a `fotoSha256`; imagens ilustrativas são rotuladas. Último slide: CTA WhatsApp/Telegram
(links só se fornecidos e oficiais) e identificação de afiliado quando aplicável. Emite só `foto_topo` e `cartao` (o validador do gerador reprova combinações de texto em `foto_cheia`).
O contrato do gerador não foi alterado; a compatibilidade é provada nos testes carregando e **renderizando** o JSON (1080×1350) com o próprio gerador, em pasta temporária.

### Etapa 5.14-A (commit 3) — revisão de conformidade

- **Impressão material e decisões** (`decisoes_v11.py`): o formato de `decisoes.json` não mudou. Uma impressão fornecida pelo próprio arquivo **nunca** é aceita (sem validação de procedência); a decisão que a traz
  fica registrada em `decisoesInvalidasNoArquivo` (ficha e `resumo.json`) com o código `impressao_fornecida_sem_procedencia`, sem ecoar o valor. A impressão é recalculada da versão revisada; sem ela,
  a decisão fica inaplicável de forma explícita (`versao_desconhecida`, `impressaoComparavel: false`).
- **Divergências A × B por valor**: o campo divergente passa a valer com o par de valores normalizado (NFKC, espaços, caixa, URL sem formatação). Mesmo campo com valor materialmente diferente = `valor_alterado`; campo
  novo = `novo`; igual ou redução continua válido. Preço e disponibilidade não entram na divergência (seguem o portão comercial).
- **Carrossel**: ficha em estado inelegível devolve relatório `status: "bloqueado"` (`estado_inelegivel`), sem exceção; `CarrosselRecusado` só para chamada inválida.

### Etapa 5.14-B1 (commit 1) — curadoria manual no contrato 1.1

Nova fonte do tipo B, **só no contrato 1.1** (`validar_produto(..., contrato="1.1")`, usado apenas por `leitor_v11`; o padrão `"1.0"` não mudou): `source.kind = curadoria_manual`,
`source.system = SuzukiOfertas-Instagram-Curadoria` e `product.provider = CURADORIA` (os três obrigatórios juntos; no contrato 1.1 o provedor `CURADORIA` é reservado e recusado para qualquer fonte do agente; o contrato 1.0 não mudou e continua aceitando esse nome em A/B). Entra só em `B/`.
**Preço nulo** (`amountCents: null`, moeda BRL, `originalAmountCents`/`verifiedAt`/`validUntil` nulos, `verification: desconhecida`) é aceito exclusivamente na curadoria, que exige `availability = unknown`, `affiliateUrl` nulo,
`publication.state = nao_publicada`, `agentPublicationEligible = false` e `blockReason = curadoria_manual_sem_verificacao_comercial` (valor exato; o detector de "sequência opaca" o recusaria, então é comparado literalmente).
`sourceRef` de cada fato = URL HTTPS (sem rede; encurtadores e origens de procedência não verificável são recusados por **nome do host**, em `curadoria_regras_v11.py`); URL válida **não** prova veracidade.
Título de risco ALTA e alegações comerciais (preço, desconto/promoção/oferta, frete grátis, estoque/disponibilidade, urgência, menor preço, % promocional) em título ou fato são rejeitados; risco MÉDIA só avisa.
Fichas sem preço mostram "sem preço verificado". Ficha continua `candidato_nao_verificado`; publicação nunca é autorizada. Limitações: heurística textual (falsos positivos/negativos), lista finita de encurtadores.
