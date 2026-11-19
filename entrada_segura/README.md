# entrada_segura (B3-A1)

Pacote **isolado** que classifica, autentica e registra a evidência de um lote de entrada antes de qualquer consumo. Testado **somente com dados
sintéticos**. **Não está integrado** a nenhum ponto de entrada do repositório (isso é a B3-A2, que exige autorização própria). Nenhum produto,
foto, autorização ou chave real existe aqui: a **âncora de produção é vazia** e as flags de dados e produtos reais permanecem `False`.

- Ponto de entrada de produção: `entrada_segura.portao.avaliar_producao(raiz_lote, arquivos, *, base_evidencia=None, pasta_autorizacao=None,
  pasta_revogacao=None)` — sem parâmetros de configuração.
- Camada de biblioteca: `portao.Portao(config).avaliar(...)` — usada pelos testes com configuração **sintética**; **não** é ponto de entrada.
- Só biblioteca padrão e `cryptography` (somente em `assinatura.py`, importada de forma preguiçosa). Sem rede, sem `argv`, sem variáveis de ambiente,
  sem arquivo de configuração, sem `__main__`.

## Regras de decisão (resumo)

Classe do lote (depende só dos dados e da procedência, nunca da autorização): `ficticio_reconhecido`, `potencialmente_real`, `desconhecido`.

| Classe | Decisão |
|---|---|
| `ficticio_reconhecido` (hosts reservados **e** conjunto de fixtures exato) | aceita, mesmo com flags `False` |
| `potencialmente_real` | aceita só com **todas** as flags reais habilitadas **e** atestado válido e atual (só na camada de biblioteca sintética); atestado válido **não** supera flag `False` |
| `desconhecido` | sempre recusada |

Qualquer erro interno ou falha ⇒ recusa (fail-closed). O relatório tem três registros separados: classificação, autorização e decisão.
`ResultadoEntrada.consumo_permitido` só é verdadeiro com decisão `aceita` **e** relatório persistido (diretório de evidência novo por execução,
nunca sobrescrito). A B3-A2 exigirá essa persistência **antes** de qualquer processamento.

## Plataformas

- **Linux/POSIX (garantia FORTE):** abertura por descritor de diretório com `O_NOFOLLOW` em cada componente, hardlinks e arquivos especiais recusados,
  lista fechada, limites de tamanho e verificação de troca durante a leitura. A **raiz informada não pode ser link simbólico** (recusada antes do
  `realpath`); os ancestrais da raiz informada pelo operador são confiáveis.
- **Windows:** a proteção real **não foi implementada** e **não é demonstrada**. A biblioteca padrão não oferece abertura sem seguir links por
  componente, `dir_fd` nem `O_NOFOLLOW`; `ctypes` e APIs nativas são proibidos aqui. Por isso `avaliar_producao` **recusa** no Windows com
  `garantia_plataforma_insuficiente`. Os testes do ramo Windows são **simulações** e não provam proteção real. **Nenhuma integração operacional Windows
  foi autorizada.** A futura B3-A2 depende de decisão específica sobre compatibilidade Windows ou ambiente Linux. Essa limitação **não** significa que
  o projeto esteja pronto para produtos reais.
- Não há *snapshot* atômico: o consumidor recebe os **bytes já lidos e verificados**, nunca um caminho.

## Modelo de ameaça

Coberto: lote forjado com metadados falsos; domínios que imitam os reservados; atestado forjado, expirado, revogado ou de outra âncora; combinação
arbitrária de arquivos reconhecidos; troca de arquivo entre a validação e o uso por processo comum; caminhos, links, hardlinks e arquivos especiais
maliciosos em POSIX; flags `False`; URLs `http`.

Não coberto: adversário que executa código no mesmo processo ou controla o sistema de arquivos continuamente; chave privada comprometida; relógio
adulterado; aprovação sem revisão; **publicação/Metricool** (fora do portão e **não declarados protegidos**); proteção em Windows; ancestrais da raiz
informada pelo operador.

## Autorização e revogação (limitações aceitas)

- Atestado externo ao lote, assinado (Ed25519 via `cryptography`), preso aos bytes exatos, escopo fechado, validade **máxima de 7 dias**, nonce.
  A assinatura prova controle da chave e integridade, **não** a revisão correta nem o direito sobre a imagem.
- A âncora (fingerprint da chave pública do aprovador) será fixada em código revisado; **P-05 (identidade do aprovador) permanece pendente**.
- Lista de revogações assinada, com carimbo de atualidade e janela máxima de 24 h; se a atualidade não puder ser comprovada, a recusa é automática.
  **Não há garantia de revogação instantânea.**
- **Tolerância de relógio, sincronização de relógios e viabilidade operacional da atualização das revogações serão reavaliadas antes do primeiro dado
  real** (e testadas antes da B3-C). A tolerância de **0 s** vale apenas para os testes desta etapa.
- Riscos conhecidos: **repetição de uma lista antiga ainda válida** dentro da janela; **estado local apagável** (a B3-A1 não persiste estado; o último
  valor de `sequencia` visto só é registrado no relatório); relógio local confiável; sem tarefa automática de renovação.

## Limites desta etapa

2 MiB por arquivo, 64 MiB por lote, 1.000 arquivos por lote. **Não são definitivos para fotografias comerciais**: a B3-B definirá limites próprios.

## Registro de fixtures

`fixtures_registro.py` guarda **conjuntos exatos** (caminhos relativos e SHA-256 literais). Combinação de arquivos reconhecidos individualmente,
subconjunto ou superconjunto não é lote confiável. Constatação para a B3-A2: lotes sem URL, com JSON ilegível ou binário (por exemplo
`produtos/exemplos_ficticios/troca`) **não** são reconhecidos pela regra da classificação; a decisão sobre eles é da B3-A2.

## Pendências da B3-A2 (nada disto foi feito)

Integrar apenas `avaliar_producao` aos pontos de entrada; alteração **específica e auditável** de `produtos/tests/test_sem_rede.py` (permitir somente a
raiz `entrada_segura`, mantendo as proibições); adaptação central dos testes dinâmicos; política para parâmetros que não são arquivos do lote;
persistência obrigatória do relatório antes do consumo; decisão sobre Windows; limites para fotografias (B3-B).

## Testes

```bash
python3 -m unittest discover -s entrada_segura/tests -t .
```

`inventario`: ver `docs/INVENTARIO_TESTES.md` e `docs/inventario_testes.csv`. A dependência está declarada em `requirements.txt` (nada a instala).
