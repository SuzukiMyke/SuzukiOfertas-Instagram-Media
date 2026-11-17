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
