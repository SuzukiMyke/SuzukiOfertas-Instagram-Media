# Campos do contrato de produtos v1 (`schemaVersion` 1.0.0)

Fonte: `CONTRATO_PRODUTOS_INSTAGRAM.md` (1.0.0-proposta). O JSON Schema (`produto.v1.schema.json`) cobre a
estrutura; as regras marcadas com † são aplicadas só por `esquema.py` (um JSON Schema não as expressa).

Um arquivo por produto, UTF-8, até 256 KiB. Datas: `AAAA-MM-DDTHH:MM:SSZ` (UTC). Chaves fora da tabela rejeitam o arquivo.

| Campo | A (`agente_publicada`) | B (`catalogo_candidato`/`api_candidato`) |
|---|---|---|
| `schemaVersion` | obrigatório; major 1 (outra major → quarentena) | idem |
| `exportId` | obrigatório (UUID) | idem |
| `exportedAt` | obrigatório; não pode estar no futuro† | idem |
| `source.kind` / `source.system` | `agente_publicada` / `SuzukiOfertas-AgenteAutomatico` | `catalogo_candidato` ou `api_candidato` / idem |
| `product.id` | obrigatório (`[A-Za-z0-9][A-Za-z0-9._-]{0,63}`) | idem |
| `product.provider` | obrigatório (`[A-Z][A-Z0-9_]{1,40}`) | idem |
| `product.store`, `product.title` (≤ 240) | obrigatórios | idem |
| `product.officialUrl` | obrigatório; HTTPS, sem credenciais/porta/IP, sem token/sessão/rastreio† | idem |
| `product.affiliateUrl` | **obrigatório** (HTTPS; sem token/sessão†) | **deve ser `null`/ausente** |
| `product.category`, `categoryOrigin` | opcionais (`fonte` \| `derivada_revisada`) | opcionais |
| `product.advertiserId` | opcional | opcional |
| `price.amountCents` | inteiro > 0 (≤ 10⁹) | idem |
| `price.currency` | `BRL` | `BRL` |
| `price.verification` | **`ao_vivo`** | `catalogo_sem_verificacao` ou `desconhecida` (nunca `ao_vivo`) |
| `price.verifiedAt`, `price.validUntil` | **obrigatórios**; `validUntil` > `verifiedAt`† | `null`/ausentes |
| `price.originalAmountCents` | opcional | opcional |
| `availability` | obrigatório (`in_stock`/`unknown`/`out_of_stock`) | idem |
| `photo` | **obrigatório** (com `usePermission`) | opcional |
| `photo.usePermission` | `confirmada`/`pendente`/`negada` (padrão `pendente`) | idem |
| `photo.url`, `origin`, `permissionRef`, `checkedAt` | opcionais; `confirmada` exige `url`+`permissionRef`+`checkedAt`† | idem |
| `verifiedFacts[]` (≤ 20) | opcional: `text`, `sourceRef`, `verifiedAt` | idem |
| `publication.state` | **`publicada`** | **`nao_publicada`** |
| `publication.publishedAt` | **obrigatório** (≤ `exportedAt`†) | `null`/ausente |
| `publication.channel` | nome público (nunca ID privado†) | `null` |
| `references[]` (≤ 20) | opcional: `label`, `url` (HTTPS) | idem |
| `eligibility.agentPublicationEligible` | obrigatório (booleano) | obrigatório e **`false`** |
| `eligibility.blockReason` | opcional | opcional |

Campos **proibidos** (nunca exportar): credenciais, tokens, chaves, conteúdo de cofre, IDs/updates/mensagens do
Telegram, ID de operador, dados pessoais, texto/mídia de terceiros, parâmetros de sessão em URLs. Como o validador usa
lista de permissão, qualquer um deles (ou qualquer campo desconhecido) rejeita o arquivo inteiro.

## Decisões e divergências (Etapa 5.8)

- **`pendente_revisao` após mudança de preço.** O contrato (§4) lista "preço mudou" sob `invalidado`; o GOAL 5.4
  manda a ficha voltar a `pendente_revisao`. Seguiu-se o GOAL; `invalidado` fica para indisponibilidade.
- **B e aprovação.** O contrato classifica "B sem verificação" como `expirado` (não pode virar conteúdo). Logo B
  nunca recebe `aprovado_para_rascunho` nem `aprovado_para_publicacao`; decisões humanas sobre B são ignoradas e
  relatadas. Para usar um candidato B é preciso uma nova exportação do tipo A.
- **Limite de validade.** `validUntil` e a janela de revalidação são **inclusivos** (válido até o instante exato).
- **`aprovado_para_publicacao` também gera fragmento de rascunho** (é superconjunto de `aprovado_para_rascunho`);
  o GOAL cita apenas `aprovado_para_rascunho`.
- **Ficha → Reel exige foto local.** O gerador de Reels lê um arquivo de imagem (`source.path`); a ficha só tem a
  URL da foto, e esta etapa não baixa imagens. O fragmento exige `foto_local` (foto já importada no repositório).
- **Manifesto.** Formato adotado: `{"manifestVersion": "1.0", "count": N, "files": [{"name", "sha256"}]}`. Com
  manifesto presente, arquivo **não listado** vai para quarentena (pode estar sendo gravado) e manifesto inválido
  põe todos os arquivos em quarentena (falha segura).
- **`source.system`** deve ser exatamente `SuzukiOfertas-AgenteAutomatico` (constante do contrato).

## Curadoria manual (contrato 1.1; Etapa 5.14-B1)

Só existe com `validar_produto(..., contrato="1.1")`; o modo 1.0 continua recusando tudo abaixo. `schemaVersion` permanece `1.0.x` e nenhum campo novo foi acrescentado ao formato externo.

| Campo | Curadoria manual (`curadoria_manual`), somente em `B/` |
|---|---|
| `source.kind` / `source.system` | `curadoria_manual` / `SuzukiOfertas-Instagram-Curadoria` |
| `product.provider` | `CURADORIA` (reservado: recusado nas demais fontes) |
| `product.affiliateUrl` | `null` |
| `price` | `{"amountCents": null, "currency": "BRL", "originalAmountCents": null, "verifiedAt": null, "validUntil": null, "verification": "desconhecida"}`; preço não nulo, se vier, segue as regras de B |
| `availability` | `unknown` |
| `verifiedFacts[].sourceRef` | URL HTTPS (sem rastreio/sessão; encurtadores e IPs recusados); `verifiedAt` obrigatório e não futuro; até 20 fatos |
| `publication.state` / `eligibility` | `nao_publicada` / `false`, `blockReason = curadoria_manual_sem_verificacao_comercial` |
| `product.title`, fatos | sem alegação comercial; título de risco ALTA recusado; MÉDIA gera aviso |
