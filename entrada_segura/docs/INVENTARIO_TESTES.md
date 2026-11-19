# Inventário dos 705 testes (B3-A1)

Gerado por análise estática (AST) **descartável e não versionada** sobre o commit-base `927f877dfde21895468c713f010fa129a14cd080`; nenhum teste foi alterado ou executado para isso. Os ids vêm do carregador `unittest` (nome da classe de execução); as chamadas são resolvidas por identidade de objeto, de forma **transitiva** pelas funções auxiliares e ganchos `setUp/setUpClass` das próprias suítes (inclusive funções passadas como argumento).

## Método e definições

Categoria principal (mutuamente exclusiva, nesta ordem de prioridade):

1. **OP** — o teste (direta ou transitivamente por auxiliares) chama ou referencia um ponto de entrada L1: `main` das CLIs `produtos`, `curadoria_b`, `orquestrador_b2`, `orquestrador_b2.entrega` e `gerador`; `curadoria_b.exportador.exportar`; `orquestrador_b2.fluxo.executar`/`entrega.entregar`; `gerador.importar.importar`; `gerador.flux.gerar`; `reel_gen.cli.main`, `reel_gen.pipeline.build/prepare/render_cta_only`; `scripts/gerar_slide.main`; ou `subprocess` sobre esses módulos.
2. **DIN** — (não OP) escreve lotes/arquivos dinamicamente (`write_text`, `write_bytes`, `gravar_lote`, `open(...,'w')`, `mkdir`, `copytree`…), inclusive em `setUp`/`setUpClass` quando o gancho escreve arquivos; criar só diretórios (`mkdir`, `tempfile`) em ganchos **não** basta (a classe `Base` de `produtos` cria diretório temporário para todos os testes, mesmo os que só validam dicionários).
3. **EST** — (não OP/DIN) usa fixtures estáticas versionadas (`exemplos_ficticios*`, `exemplos/carrossel_exemplo.json`).
4. **INT** — todo o resto: lógica interna pura (L0).

Decisões sobre chamadas ambíguas (a heurística preliminar classificava `gerar` do gerador como OP):

- `gerador.flux.gerar` é o ponto E7 (FLUX) ⇒ OP. `gerador.carrossel.gerar` **não** é ponto de entrada: é função de biblioteca (L0) usada pela CLI `gerador` e por `orquestrador_b2.executar`; o portão fica na CLI/orquestrador. Testes que só a chamam são DIN/EST/INT conforme o restante.
- Chamadas diretas a `processar_v11`, `ler_lote`, `ler_pasta`, `construir_lote` e demais funções de `produtos`/`curadoria_b` são **L0** (sem portão); só as CLIs e as funções públicas listadas acima são OP.
- `orquestrador_b2.entrega` (B2R) foi incluída como E4 por ser a entrega operacional do orquestrador.

Marcadores complementares (não entram na soma): `fixture_dinamica`, `fixture_estatica`, `entrada_operacional`, `guarda_estatica_ou_golden_ou_flags`, `http_negativo`.

Impacto esperado da B3-A2: `nenhum` (L0 sem portão); `baixo/central` (OP com lote gerado por `Base`/`BaseV11`/`gravar_lote` ou fixture estática em conjunto registrado); `adaptar` (OP que monta o próprio lote, e a única alteração prevista em `test_sem_rede.py::test_apenas_biblioteca_padrao`); `exige decisão` (E8/reels, política ainda não definida).

## Resumo por suíte e verificação aritmética

| Suíte | Total | INT | DIN | EST | OP | Soma |
|---|---|---|---|---|---|---|
| `produtos` | 417 | 74 | 320 | 11 | 12 | 417 |
| `curadoria_b` | 39 | 5 | 0 | 2 | 32 | 39 |
| `orquestrador_b2` | 68 | 16 | 0 | 6 | 46 | 68 |
| `tests/gerador+fundo` | 42 | 22 | 5 | 1 | 14 | 42 |
| `tests/b2r_compat_layouts` | 47 | 44 | 1 | 1 | 1 | 47 |
| `tests/b2r_referencia_regressao` | 22 | 0 | 0 | 0 | 22 | 22 |
| `reels` | 70 | 44 | 0 | 0 | 26 | 70 |
| **Total** | **705** | **205** | **326** | **21** | **153** | **705** |

Verificação: INT + DIN + EST + OP = 205 + 326 + 21 + 153 = **705**; ids únicos: **705**.

Comparação **informativa** com a heurística preliminar (INT 389, DIN 184, EST 4, OP 128): os números definitivos acima **não** foram forçados a coincidir; a diferença vem da resolução transitiva por identidade de objeto e das decisões listadas.

| Suíte | Preliminar (total/INT/DIN/EST/OP) | Definitivo (INT/DIN/EST/OP) |
|---|---|---|
| `produtos` | 417/230/131/0/56 | 74/320/11/12 |
| `curadoria_b` | 39/7/4/0/28 | 5/0/2/32 |
| `orquestrador_b2` | 68/23/18/3/24 | 16/0/6/46 |
| `tests/gerador+fundo` | 42/19/8/1/14 | 22/5/1/14 |
| `tests/b2r_compat_layouts` | 47/28/17/0/2 | 44/1/1/1 |
| `tests/b2r_referencia_regressao` | 22/18/4/0/0 | 0/0/0/22 |
| `reels` | 70/64/2/0/4 | 44/0/0/26 |

Marcadores (contagem): `entrada_operacional` 153, `fixture_dinamica` 372, `fixture_estatica` 128, `guarda_estatica_ou_golden_ou_flags` 16, `http_negativo` 9.

Impacto na B3-A2: `adaptar` 9, `baixo/central` 119, `exige decisão` 26, `nenhum` 551.

## Reconfirmação do achado sobre HTTP

Busca por `http://` no commit-base: **nenhum** arquivo de fixture estática (JSON, MD, TXT, JPG…) contém a cadeia. As ocorrências estão só em testes `.py`: `produtos/tests/{test_esquema,test_exemplos,test_fichas,test_v11_curadoria,test_v11_carrossel}.py`, `curadoria_b/tests/test_curadoria_b.py` e `orquestrador_b2/tests/test_orquestrador_b2.py`, todas como entradas **negativas** (a lista do GOAL citava seis arquivos; `test_fichas.py` também tem uma ocorrência: uma string de injeção de markdown, igualmente negativa). **Nenhuma fixture histórica depende de HTTP.** Testes marcados `http_negativo`: 9.

## Conjuntos de fixtures propostos (a registrar em `entrada_segura/fixtures_registro.py`)

Cada conjunto abaixo é um `ConjuntoFixture` exato (todos os arquivos da pasta, caminhos relativos ao lote, com hashes literais). A revisão é do ChatGPT/usuário.

| Conjunto (`id`) | Pasta-base | Arquivos |
|---|---|---|
| `produtos/exemplos_ficticios` | `produtos/exemplos_ficticios` | 17 |
| `produtos/exemplos_ficticios/troca` | `produtos/exemplos_ficticios/troca` | 16 |
| `produtos/exemplos_ficticios/decisoes` | `produtos/exemplos_ficticios/decisoes` | 1 |
| `produtos/exemplos_ficticios_v1_1` | `produtos/exemplos_ficticios_v1_1` | 11 |
| `produtos/exemplos_ficticios_v1_1/exportacoes` | `produtos/exemplos_ficticios_v1_1/exportacoes` | 5 |
| `produtos/exemplos_ficticios_v1_1/exportacoes/A` | `produtos/exemplos_ficticios_v1_1/exportacoes/A` | 3 |
| `produtos/exemplos_ficticios_v1_1/exportacoes/B` | `produtos/exemplos_ficticios_v1_1/exportacoes/B` | 2 |
| `produtos/exemplos_ficticios_v1_1/decisoes` | `produtos/exemplos_ficticios_v1_1/decisoes` | 3 |
| `produtos/exemplos_ficticios_v1_1/fotos` | `produtos/exemplos_ficticios_v1_1/fotos` | 2 |
| `curadoria_b/exemplos_ficticios` | `curadoria_b/exemplos_ficticios` | 1 |
| `orquestrador_b2/exemplos_ficticios` | `orquestrador_b2/exemplos_ficticios` | 3 |
| `orquestrador_b2/exemplos_ficticios/ficha_tecnologia_fone.json` | `orquestrador_b2/exemplos_ficticios` | 1 |
| `orquestrador_b2/exemplos_ficticios/ficha_casa_cozinha_panela.json` | `orquestrador_b2/exemplos_ficticios` | 1 |
| `orquestrador_b2/exemplos_ficticios/ficha_ferramentas_furadeira.json` | `orquestrador_b2/exemplos_ficticios` | 1 |
| `exemplos` | `exemplos` | 1 |

Regras: conjuntos **exatos** (mesmos caminhos e hashes, nem a mais nem a menos); combinação arbitrária, subconjunto, superconjunto ou mistura entre conjuntos ⇒ sem procedência. Fixtures dinâmicas dos testes existentes **não** entram no registro (recebem procedência pelo mecanismo isolado de teste, B3-A2).

## Tabela por teste (705 linhas; o CSV traz também marcadores, pontos de entrada e estratégia completa)

| # | Id | Suíte | Cat. | Impacto B3-A2 | Marcadores |
|---|---|---|---|---|---|
| 1 | `produtos/tests/test_esquema.py::FontesATest::test_a_exige_verificacao_publicacao_e_afiliado` | produtos | INT | nenhum | — |
| 2 | `produtos/tests/test_esquema.py::FontesATest::test_b_nao_exige_afiliado_nem_verificacao_nem_foto` | produtos | INT | nenhum | — |
| 3 | `produtos/tests/test_esquema.py::FontesATest::test_b_nao_pode_ser_publicada_nem_elegivel` | produtos | INT | nenhum | — |
| 4 | `produtos/tests/test_esquema.py::FontesATest::test_source_kind_inconsistente_com_campos` | produtos | INT | nenhum | — |
| 5 | `produtos/tests/test_esquema.py::InvalidosTest::test_cada_caso_invalido_e_rejeitado_com_motivo_claro` | produtos | INT | nenhum | — |
| 6 | `produtos/tests/test_esquema.py::InvalidosTest::test_dados_insuficientes_lista_campos_faltantes` | produtos | INT | nenhum | — |
| 7 | `produtos/tests/test_esquema.py::InvalidosTest::test_major_desconhecida_vai_para_quarentena` | produtos | INT | nenhum | — |
| 8 | `produtos/tests/test_esquema.py::InvalidosTest::test_sem_schemaversion_ou_exportid_e_ignorado` | produtos | INT | nenhum | — |
| 9 | `produtos/tests/test_esquema.py::ProibidosTest::test_campos_desconhecidos_e_comentarios_rejeitam` | produtos | INT | nenhum | — |
| 10 | `produtos/tests/test_esquema.py::ProibidosTest::test_campos_proibidos_rejeitam_o_arquivo` | produtos | INT | nenhum | — |
| 11 | `produtos/tests/test_esquema.py::ProibidosTest::test_chave_com_valor_estranho_e_sanitizada_na_mensagem` | produtos | INT | nenhum | — |
| 12 | `produtos/tests/test_esquema.py::ProibidosTest::test_mensagens_nao_ecoam_valores_suspeitos` | produtos | INT | nenhum | — |
| 13 | `produtos/tests/test_esquema.py::ValidosTest::test_a_e_b_validos` | produtos | INT | nenhum | — |
| 14 | `produtos/tests/test_esquema.py::ValidosTest::test_aviso_categoria_ausente` | produtos | INT | nenhum | — |
| 15 | `produtos/tests/test_esquema.py::ValidosTest::test_b_api_candidato_e_foto_opcional` | produtos | INT | nenhum | — |
| 16 | `produtos/tests/test_esquema.py::ValidosTest::test_dados_normalizados_so_tem_campos_permitidos` | produtos | INT | nenhum | — |
| 17 | `produtos/tests/test_exemplos.py::EsquemaJsonTest::test_chaves_do_json_schema_coincidem_com_a_lista_de_permissao` | produtos | INT | nenhum | — |
| 18 | `produtos/tests/test_exemplos.py::EsquemaJsonTest::test_json_schema_aceita_validos_e_recusa_invalidos_quando_jsonschema_existe` | produtos | EST | nenhum | fixture estatica;http negativo |
| 19 | `produtos/tests/test_exemplos.py::EsquemaJsonTest::test_schema_version_documentada` | produtos | INT | nenhum | — |
| 20 | `produtos/tests/test_exemplos.py::ExemplosTest::test_a004_aprovacao_invalidada_por_preco` | produtos | EST | nenhum | fixture estatica |
| 21 | `produtos/tests/test_exemplos.py::ExemplosTest::test_estados_esperados` | produtos | EST | nenhum | fixture estatica |
| 22 | `produtos/tests/test_exemplos.py::ExemplosTest::test_exemplos_nao_foram_alterados` | produtos | EST | nenhum | fixture estatica |
| 23 | `produtos/tests/test_exemplos.py::ExemplosTest::test_exemplos_sao_inequivocamente_ficticios` | produtos | EST | nenhum | fixture estatica |
| 24 | `produtos/tests/test_exemplos.py::ExemplosTest::test_ignorados_em_silencio_e_historico_de_a004` | produtos | EST | nenhum | fixture estatica |
| 25 | `produtos/tests/test_exemplos.py::ExemplosTest::test_rejeitados_esperados` | produtos | EST | nenhum | fixture estatica |
| 26 | `produtos/tests/test_fichas.py::FichasTest::test_conteudo_da_ficha_a` | produtos | DIN | nenhum | fixture dinamica |
| 27 | `produtos/tests/test_fichas.py::FichasTest::test_dados_insuficientes_no_relatorio_de_rejeitados` | produtos | DIN | nenhum | fixture dinamica |
| 28 | `produtos/tests/test_fichas.py::FichasTest::test_ficha_b_e_sem_foto_autorizada_e_com_pendencias` | produtos | DIN | nenhum | fixture dinamica |
| 29 | `produtos/tests/test_fichas.py::FichasTest::test_ficha_nao_expoe_campos_proibidos` | produtos | DIN | nenhum | fixture dinamica |
| 30 | `produtos/tests/test_fichas.py::FichasTest::test_ficha_so_contem_dados_vindos_da_lista_de_permissao` | produtos | DIN | nenhum | fixture dinamica |
| 31 | `produtos/tests/test_fichas.py::FichasTest::test_gera_json_e_markdown_por_produto` | produtos | DIN | nenhum | fixture dinamica |
| 32 | `produtos/tests/test_fichas.py::FichasTest::test_markdown_neutraliza_marcacao_e_html` | produtos | DIN | nenhum | fixture dinamica;http negativo |
| 33 | `produtos/tests/test_fichas.py::FichasTest::test_reais` | produtos | INT | nenhum | — |
| 34 | `produtos/tests/test_fichas.py::FichasTest::test_resumo_conta_por_estado_e_destino` | produtos | DIN | nenhum | fixture dinamica |
| 35 | `produtos/tests/test_fichas.py::FichasTest::test_saida_e_deterministica_e_limpa_fichas_antigas` | produtos | DIN | nenhum | fixture dinamica |
| 36 | `produtos/tests/test_fichas.py::FichasTest::test_saida_nao_depende_do_relogio_do_sistema` | produtos | DIN | nenhum | fixture dinamica |
| 37 | `produtos/tests/test_golden_modo_1_0.py::GoldenModo10Test::test_argumentos_do_modo_1_1_sem_contrato_1_1_sao_recusados` | produtos | OP | baixo/central | fixture estatica;entrada operacional;guarda estatica ou golden ou flags |
| 38 | `produtos/tests/test_golden_modo_1_0.py::GoldenModo10Test::test_cli_sem_contrato_e_com_contrato_1_0_sao_identicos` | produtos | OP | baixo/central | fixture estatica;entrada operacional;guarda estatica ou golden ou flags |
| 39 | `produtos/tests/test_golden_modo_1_0.py::GoldenModo10Test::test_contrato_padrao_continua_1_0_e_recusa_1_1_neste_fluxo` | produtos | EST | nenhum | fixture estatica;guarda estatica ou golden ou flags |
| 40 | `produtos/tests/test_golden_modo_1_0.py::GoldenModo10Test::test_golden_e_deterministico` | produtos | EST | nenhum | fixture estatica;guarda estatica ou golden ou flags |
| 41 | `produtos/tests/test_golden_modo_1_0.py::GoldenModo10Test::test_hashes_golden_identicos` | produtos | EST | nenhum | fixture estatica;guarda estatica ou golden ou flags |
| 42 | `produtos/tests/test_leitor.py::LeitorTest::test_arquivo_grande_demais_e_recusado` | produtos | DIN | nenhum | fixture dinamica |
| 43 | `produtos/tests/test_leitor.py::LeitorTest::test_arquivo_nao_listado_no_manifesto_fica_em_quarentena` | produtos | DIN | nenhum | fixture dinamica |
| 44 | `produtos/tests/test_leitor.py::LeitorTest::test_arquivos_originais_ficam_intactos` | produtos | DIN | nenhum | fixture dinamica |
| 45 | `produtos/tests/test_leitor.py::LeitorTest::test_ignora_tmp_ocultos_nao_json_e_subpastas` | produtos | DIN | nenhum | fixture dinamica |
| 46 | `produtos/tests/test_leitor.py::LeitorTest::test_json_estrito_chave_duplicada_nan_e_utf8` | produtos | DIN | nenhum | fixture dinamica |
| 47 | `produtos/tests/test_leitor.py::LeitorTest::test_json_truncado_vai_para_quarentena` | produtos | DIN | nenhum | fixture dinamica |
| 48 | `produtos/tests/test_leitor.py::LeitorTest::test_le_validos_em_ordem_deterministica` | produtos | DIN | nenhum | fixture dinamica |
| 49 | `produtos/tests/test_leitor.py::LeitorTest::test_link_simbolico_e_ignorado` | produtos | DIN | nenhum | fixture dinamica |
| 50 | `produtos/tests/test_leitor.py::LeitorTest::test_manifesto_avisa_arquivo_ausente_e_contagem` | produtos | DIN | nenhum | fixture dinamica |
| 51 | `produtos/tests/test_leitor.py::LeitorTest::test_manifesto_com_hash_errado_vai_para_quarentena` | produtos | DIN | nenhum | fixture dinamica |
| 52 | `produtos/tests/test_leitor.py::LeitorTest::test_manifesto_correto_aceita` | produtos | DIN | nenhum | fixture dinamica |
| 53 | `produtos/tests/test_leitor.py::LeitorTest::test_manifesto_invalido_poe_tudo_em_quarentena` | produtos | DIN | nenhum | fixture dinamica |
| 54 | `produtos/tests/test_leitor.py::LeitorTest::test_pasta_inexistente` | produtos | INT | nenhum | — |
| 55 | `produtos/tests/test_leitor.py::LeitorTest::test_relatorio_de_rejeitados_nao_copia_conteudo` | produtos | DIN | nenhum | fixture dinamica |
| 56 | `produtos/tests/test_leitor.py::LeitorTest::test_saida_dentro_da_troca_e_recusada` | produtos | DIN | nenhum | fixture dinamica |
| 57 | `produtos/tests/test_reel_fragmento.py::FragmentoTest::test_aprovado_para_publicacao_tambem_gera_rascunho` | produtos | DIN | nenhum | fixture dinamica |
| 58 | `produtos/tests/test_reel_fragmento.py::FragmentoTest::test_avisos_de_titulo_longo_e_categoria_ausente` | produtos | DIN | nenhum | fixture dinamica |
| 59 | `produtos/tests/test_reel_fragmento.py::FragmentoTest::test_fragmento_valido_contra_o_formato_real` | produtos | DIN | nenhum | fixture dinamica |
| 60 | `produtos/tests/test_reel_fragmento.py::FragmentoTest::test_nao_altera_a_config_base_nem_o_gerador` | produtos | DIN | nenhum | fixture dinamica |
| 61 | `produtos/tests/test_reel_fragmento.py::FragmentoTest::test_politica_de_conteudo_do_gerador_e_aplicada` | produtos | DIN | nenhum | fixture dinamica |
| 62 | `produtos/tests/test_reel_fragmento.py::FragmentoTest::test_preco_fica_fora_do_video` | produtos | DIN | nenhum | fixture dinamica |
| 63 | `produtos/tests/test_reel_fragmento.py::FragmentoTest::test_recusa_estados_sem_aprovacao_humana` | produtos | DIN | nenhum | fixture dinamica |
| 64 | `produtos/tests/test_reel_fragmento.py::FragmentoTest::test_recusa_foto_local_ausente_ou_insegura` | produtos | DIN | nenhum | fixture dinamica |
| 65 | `produtos/tests/test_reel_fragmento.py::FragmentoTest::test_recusa_sem_foto_autorizada_nem_com_ia` | produtos | DIN | nenhum | fixture dinamica |
| 66 | `produtos/tests/test_reel_fragmento.py::FragmentoTest::test_validador_real_rejeita_fragmento_fora_do_formato` | produtos | DIN | nenhum | fixture dinamica |
| 67 | `produtos/tests/test_registro_estados.py::DecisoesTest::test_aprovacao_para_publicacao_so_registra_autorizacao` | produtos | DIN | nenhum | fixture dinamica |
| 68 | `produtos/tests/test_registro_estados.py::DecisoesTest::test_aprovacao_sobrevive_a_nova_versao_com_mesmo_preco` | produtos | DIN | nenhum | fixture dinamica |
| 69 | `produtos/tests/test_registro_estados.py::DecisoesTest::test_arquivo_de_decisoes_ausente_ou_corrompido_nao_aprova` | produtos | DIN | nenhum | fixture dinamica |
| 70 | `produtos/tests/test_registro_estados.py::DecisoesTest::test_b_nunca_e_aprovado` | produtos | DIN | nenhum | fixture dinamica |
| 71 | `produtos/tests/test_registro_estados.py::DecisoesTest::test_codigo_nunca_grava_o_arquivo_de_decisoes` | produtos | DIN | nenhum | fixture dinamica |
| 72 | `produtos/tests/test_registro_estados.py::DecisoesTest::test_decisao_de_data_futura_ou_anterior_a_exportacao_e_ignorada` | produtos | DIN | nenhum | fixture dinamica |
| 73 | `produtos/tests/test_registro_estados.py::DecisoesTest::test_decisao_de_outra_versao_desconhecida_e_ignorada` | produtos | DIN | nenhum | fixture dinamica |
| 74 | `produtos/tests/test_registro_estados.py::DecisoesTest::test_decisao_humana_aprova_para_rascunho` | produtos | DIN | nenhum | fixture dinamica |
| 75 | `produtos/tests/test_registro_estados.py::DecisoesTest::test_decisoes_invalidas_sao_ignoradas_e_relatadas` | produtos | DIN | nenhum | fixture dinamica |
| 76 | `produtos/tests/test_registro_estados.py::DecisoesTest::test_incompleto_e_invalidado_nao_aceitam_aprovacao` | produtos | DIN | nenhum | fixture dinamica |
| 77 | `produtos/tests/test_registro_estados.py::DecisoesTest::test_mudanca_de_preco_invalida_aprovacao_anterior` | produtos | DIN | nenhum | fixture dinamica |
| 78 | `produtos/tests/test_registro_estados.py::DecisoesTest::test_nenhuma_transicao_automatica_para_aprovado` | produtos | INT | nenhum | — |
| 79 | `produtos/tests/test_registro_estados.py::DecisoesTest::test_preco_que_volta_ao_valor_aprovado_nao_reativa_aprovacao` | produtos | DIN | nenhum | fixture dinamica |
| 80 | `produtos/tests/test_registro_estados.py::DecisoesTest::test_rejeicao_humana` | produtos | DIN | nenhum | fixture dinamica |
| 81 | `produtos/tests/test_registro_estados.py::DecisoesTest::test_sem_decisao_nenhuma_ficha_e_aprovada` | produtos | INT | nenhum | — |
| 82 | `produtos/tests/test_registro_estados.py::DecisoesTest::test_vale_a_decisao_mais_recente` | produtos | DIN | nenhum | fixture dinamica |
| 83 | `produtos/tests/test_registro_estados.py::DeduplicacaoTest::test_arquivamento_por_idade_e_parametro` | produtos | INT | nenhum | — |
| 84 | `produtos/tests/test_registro_estados.py::DeduplicacaoTest::test_chave_e_provider_mais_id` | produtos | INT | nenhum | — |
| 85 | `produtos/tests/test_registro_estados.py::DeduplicacaoTest::test_empate_de_exported_at_e_deterministico` | produtos | INT | nenhum | — |
| 86 | `produtos/tests/test_registro_estados.py::DeduplicacaoTest::test_mantem_o_mais_recente_e_preserva_historico` | produtos | INT | nenhum | — |
| 87 | `produtos/tests/test_registro_estados.py::DeduplicacaoTest::test_mesmo_export_id_em_dois_arquivos_e_registrado` | produtos | INT | nenhum | — |
| 88 | `produtos/tests/test_registro_estados.py::DeduplicacaoTest::test_mudanca_de_preco_e_registrada_na_avaliacao` | produtos | INT | nenhum | — |
| 89 | `produtos/tests/test_registro_estados.py::DeduplicacaoTest::test_versao_antiga_arquivada_nao_vira_vigente` | produtos | INT | nenhum | — |
| 90 | `produtos/tests/test_registro_estados.py::ExpiracaoTest::test_b_e_sempre_sem_verificacao` | produtos | INT | nenhum | — |
| 91 | `produtos/tests/test_registro_estados.py::ExpiracaoTest::test_dentro_no_limite_e_fora_de_valid_until` | produtos | INT | nenhum | — |
| 92 | `produtos/tests/test_registro_estados.py::ExpiracaoTest::test_expirado_vence_a_aprovacao_humana` | produtos | DIN | nenhum | fixture dinamica |
| 93 | `produtos/tests/test_registro_estados.py::ExpiracaoTest::test_indisponivel_invalida` | produtos | INT | nenhum | — |
| 94 | `produtos/tests/test_registro_estados.py::ExpiracaoTest::test_padrao_de_revalidacao_e_24h` | produtos | INT | nenhum | — |
| 95 | `produtos/tests/test_registro_estados.py::ExpiracaoTest::test_revalidacao_de_24h_padrao_no_limite_e_fora` | produtos | INT | nenhum | — |
| 96 | `produtos/tests/test_registro_estados.py::ExpiracaoTest::test_revalidacao_e_parametro_configuravel` | produtos | INT | nenhum | — |
| 97 | `produtos/tests/test_registro_estados.py::FotoTest::test_foto_pendente_ou_negada_deixa_a_ficha_incompleta` | produtos | INT | nenhum | — |
| 98 | `produtos/tests/test_registro_estados.py::FotoTest::test_padrao_da_permissao_e_pendente` | produtos | INT | nenhum | — |
| 99 | `produtos/tests/test_registro_estados.py::FotoTest::test_situacao_traz_aviso_de_sem_foto_autorizada` | produtos | INT | nenhum | — |
| 100 | `produtos/tests/test_registro_estados.py::FotoTest::test_so_confirmada_e_utilizavel` | produtos | INT | nenhum | — |
| 101 | `produtos/tests/test_sem_rede.py::SemRedeTest::test_a_trava_de_rede_dos_testes_funciona` | produtos | INT | nenhum | guarda estatica ou golden ou flags |
| 102 | `produtos/tests/test_sem_rede.py::SemRedeTest::test_apenas_biblioteca_padrao` | produtos | INT | adaptar | guarda estatica ou golden ou flags |
| 103 | `produtos/tests/test_sem_rede.py::SemRedeTest::test_modulo_de_fragmento_so_importa_config_e_regras_do_gerador` | produtos | INT | nenhum | guarda estatica ou golden ou flags |
| 104 | `produtos/tests/test_sem_rede.py::SemRedeTest::test_nenhum_modulo_acessa_ambiente_cofre_ou_agente` | produtos | INT | nenhum | guarda estatica ou golden ou flags |
| 105 | `produtos/tests/test_sem_rede.py::SemRedeTest::test_nenhum_modulo_importa_rede_processos_ou_banco` | produtos | INT | nenhum | guarda estatica ou golden ou flags |
| 106 | `produtos/tests/test_sem_rede.py::SemRedeTest::test_pipeline_completo_roda_com_rede_bloqueada` | produtos | EST | nenhum | fixture estatica;guarda estatica ou golden ou flags |
| 107 | `produtos/tests/test_v11_avaliacao.py::ConfiguracaoTest::test_estados_do_modo_1_0_nao_mudaram` | produtos | DIN | nenhum | fixture dinamica |
| 108 | `produtos/tests/test_v11_avaliacao.py::ConfiguracaoTest::test_outros_parametros_e_contrato` | produtos | DIN | nenhum | fixture dinamica |
| 109 | `produtos/tests/test_v11_avaliacao.py::ConfiguracaoTest::test_teto_de_24h_nao_pode_ser_desativado_nem_aumentado` | produtos | DIN | nenhum | fixture dinamica |
| 110 | `produtos/tests/test_v11_avaliacao.py::DecisoesHumanasTest::test_aprovacao_humana_vinculada_a_versao` | produtos | DIN | nenhum | fixture dinamica |
| 111 | `produtos/tests/test_v11_avaliacao.py::DecisoesHumanasTest::test_aprovacao_nao_vale_se_estado_automatico_nao_permite` | produtos | DIN | nenhum | fixture dinamica |
| 112 | `produtos/tests/test_v11_avaliacao.py::DecisoesHumanasTest::test_decisao_de_versao_desconhecida_e_ignorada` | produtos | DIN | nenhum | fixture dinamica |
| 113 | `produtos/tests/test_v11_avaliacao.py::DecisoesHumanasTest::test_mudanca_de_identidade_invalida_aprovacao_em_a_e_em_b` | produtos | DIN | nenhum | fixture dinamica |
| 114 | `produtos/tests/test_v11_avaliacao.py::DecisoesHumanasTest::test_mudanca_de_loja_e_url_oficial_tambem_sao_identidade` | produtos | DIN | nenhum | fixture dinamica |
| 115 | `produtos/tests/test_v11_avaliacao.py::DecisoesHumanasTest::test_mudanca_de_preco_invalida_aprovacao_de_publicacao_de_a` | produtos | DIN | nenhum | fixture dinamica |
| 116 | `produtos/tests/test_v11_avaliacao.py::DecisoesHumanasTest::test_rejeicao_humana_vale` | produtos | DIN | nenhum | fixture dinamica |
| 117 | `produtos/tests/test_v11_avaliacao.py::DecisoesHumanasTest::test_sem_decisao_nada_e_aprovado_e_autor_automatico_e_recusado` | produtos | DIN | nenhum | fixture dinamica |
| 118 | `produtos/tests/test_v11_avaliacao.py::FatosTest::test_fato_com_data_futura_e_rejeitado_na_validacao` | produtos | DIN | nenhum | fixture dinamica |
| 119 | `produtos/tests/test_v11_avaliacao.py::FatosTest::test_fatos_frescos_e_antigos` | produtos | DIN | nenhum | fixture dinamica |
| 120 | `produtos/tests/test_v11_avaliacao.py::FatosTest::test_indicio_de_alteracao_coloca_fatos_em_revisao_antes_dos_30_dias` | produtos | DIN | nenhum | fixture dinamica |
| 121 | `produtos/tests/test_v11_avaliacao.py::FatosTest::test_mudanca_de_preco_nao_e_indicio_de_alteracao_de_fatos` | produtos | DIN | nenhum | fixture dinamica |
| 122 | `produtos/tests/test_v11_avaliacao.py::FatosTest::test_regra_dormente_sem_fatos` | produtos | DIN | nenhum | fixture dinamica |
| 123 | `produtos/tests/test_v11_avaliacao.py::FonteBTest::test_a_prevalece_sobre_b_para_o_mesmo_provedor_e_id` | produtos | DIN | nenhum | fixture dinamica |
| 124 | `produtos/tests/test_v11_avaliacao.py::FonteBTest::test_b_aceita_rascunho_editorial_sem_foto` | produtos | DIN | nenhum | fixture dinamica |
| 125 | `produtos/tests/test_v11_avaliacao.py::FonteBTest::test_b_e_candidato_nao_verificado_sem_preco_exibido` | produtos | DIN | nenhum | fixture dinamica |
| 126 | `produtos/tests/test_v11_avaliacao.py::FonteBTest::test_b_nunca_e_aprovada_para_publicacao` | produtos | DIN | nenhum | fixture dinamica |
| 127 | `produtos/tests/test_v11_avaliacao.py::FonteBTest::test_mudanca_de_preco_em_b_nao_invalida_aprovacao_editorial` | produtos | DIN | nenhum | fixture dinamica |
| 128 | `produtos/tests/test_v11_avaliacao.py::ValidadeTest::test_dentro_da_validade_com_foto_humana_e_pendente_revisao` | produtos | DIN | nenhum | fixture dinamica |
| 129 | `produtos/tests/test_v11_avaliacao.py::ValidadeTest::test_expirado_tem_precedencia_sobre_foto_ausente` | produtos | DIN | nenhum | fixture dinamica |
| 130 | `produtos/tests/test_v11_avaliacao.py::ValidadeTest::test_indisponivel_invalida_e_sem_foto_humana_fica_incompleto` | produtos | DIN | nenhum | fixture dinamica |
| 131 | `produtos/tests/test_v11_avaliacao.py::ValidadeTest::test_janela_menor_que_24h_e_permitida` | produtos | DIN | nenhum | fixture dinamica |
| 132 | `produtos/tests/test_v11_avaliacao.py::ValidadeTest::test_limite_de_validuntil_e_inclusivo` | produtos | DIN | nenhum | fixture dinamica |
| 133 | `produtos/tests/test_v11_avaliacao.py::ValidadeTest::test_permissao_exportada_pelo_agente_nao_concede_foto` | produtos | DIN | nenhum | fixture dinamica |
| 134 | `produtos/tests/test_v11_avaliacao.py::ValidadeTest::test_teto_de_24h_da_verificacao_mesmo_com_validuntil_maior` | produtos | DIN | nenhum | fixture dinamica |
| 135 | `produtos/tests/test_v11_carrossel.py::CompatibilidadeComGeradorTest::test_carregador_do_gerador_aceita_o_json` | produtos | DIN | nenhum | fixture dinamica |
| 136 | `produtos/tests/test_v11_carrossel.py::CompatibilidadeComGeradorTest::test_foto_cheia_e_aceita_pelo_gerador_mas_nao_e_emitida_aqui` | produtos | INT | nenhum | — |
| 137 | `produtos/tests/test_v11_carrossel.py::CompatibilidadeComGeradorTest::test_json_nao_altera_o_contrato_do_gerador` | produtos | INT | nenhum | — |
| 138 | `produtos/tests/test_v11_carrossel.py::CompatibilidadeComGeradorTest::test_pior_caso_de_texto_nos_layouts_emitidos_cabe_no_gerador` | produtos | OP | baixo/central | entrada operacional |
| 139 | `produtos/tests/test_v11_carrossel.py::CompatibilidadeComGeradorTest::test_renderizacao_com_foto_real_autorizada_e_hash_conferido_de_ponta_a_ponta` | produtos | OP | baixo/central | fixture dinamica;entrada operacional |
| 140 | `produtos/tests/test_v11_carrossel.py::CompatibilidadeComGeradorTest::test_renderizacao_temporaria_1080x1350_com_ilustrativa` | produtos | OP | baixo/central | fixture dinamica;entrada operacional |
| 141 | `produtos/tests/test_v11_carrossel.py::CtaELinksTest::test_identificacao_de_afiliado_so_quando_aplicavel` | produtos | DIN | nenhum | fixture dinamica |
| 142 | `produtos/tests/test_v11_carrossel.py::CtaELinksTest::test_links_fora_do_padrao_oficial_bloqueiam` | produtos | DIN | nenhum | fixture dinamica;http negativo |
| 143 | `produtos/tests/test_v11_carrossel.py::CtaELinksTest::test_sem_links_o_cta_existe_mas_nada_e_inventado` | produtos | DIN | nenhum | fixture dinamica |
| 144 | `produtos/tests/test_v11_carrossel.py::CtaELinksTest::test_ultimo_slide_e_cta_para_whatsapp_e_telegram_com_links_fornecidos` | produtos | DIN | nenhum | fixture dinamica |
| 145 | `produtos/tests/test_v11_carrossel.py::EstadosInelegiveisTest::test_chamadas_invalidas` | produtos | DIN | nenhum | fixture dinamica |
| 146 | `produtos/tests/test_v11_carrossel.py::EstadosInelegiveisTest::test_estados_inelegiveis_voltam_como_bloqueio_explicito_sem_conteudo` | produtos | DIN | nenhum | fixture dinamica |
| 147 | `produtos/tests/test_v11_carrossel.py::FatosTest::test_limite_de_fatos_por_carrossel` | produtos | DIN | nenhum | fixture dinamica |
| 148 | `produtos/tests/test_v11_carrossel.py::FatosTest::test_so_fatos_frescos_nao_truncados_e_sem_termo_comercial` | produtos | DIN | nenhum | fixture dinamica |
| 149 | `produtos/tests/test_v11_carrossel.py::FonteATest::test_aprovacao_editorial_nao_e_validade_comercial` | produtos | DIN | nenhum | fixture dinamica |
| 150 | `produtos/tests/test_v11_carrossel.py::FonteATest::test_aprovado_para_publicacao_nunca_e_definido_pela_funcao` | produtos | DIN | nenhum | fixture dinamica |
| 151 | `produtos/tests/test_v11_carrossel.py::FonteATest::test_desconto_disponibilidade_e_oferta_com_texto_do_chamador` | produtos | DIN | nenhum | fixture dinamica |
| 152 | `produtos/tests/test_v11_carrossel.py::FonteATest::test_desconto_sem_preco_original_e_omitido` | produtos | DIN | nenhum | fixture dinamica |
| 153 | `produtos/tests/test_v11_carrossel.py::FonteATest::test_janela_expirada_bloqueia_essencial_e_omite_acessoria_registrando` | produtos | DIN | nenhum | fixture dinamica |
| 154 | `produtos/tests/test_v11_carrossel.py::FonteATest::test_janela_valida_permite_preco` | produtos | DIN | nenhum | fixture dinamica |
| 155 | `produtos/tests/test_v11_carrossel.py::FonteATest::test_margem_e_limite_inclusivo_do_horario_efetivo` | produtos | DIN | nenhum | fixture dinamica |
| 156 | `produtos/tests/test_v11_carrossel.py::FonteATest::test_menor_preco_exige_prova` | produtos | DIN | nenhum | fixture dinamica |
| 157 | `produtos/tests/test_v11_carrossel.py::FonteATest::test_sem_preco_aprovado_ou_com_preco_diferente_bloqueia` | produtos | DIN | nenhum | fixture dinamica |
| 158 | `produtos/tests/test_v11_carrossel.py::FonteBTest::test_b_aprovada_para_rascunho_tambem_e_elegivel` | produtos | DIN | nenhum | fixture dinamica |
| 159 | `produtos/tests/test_v11_carrossel.py::FonteBTest::test_b_candidato_gera_so_rascunho_editorial_sem_nenhuma_informacao_comercial` | produtos | DIN | nenhum | fixture dinamica |
| 160 | `produtos/tests/test_v11_carrossel.py::FonteBTest::test_b_com_alegacao_essencial_bloqueia_e_acessoria_e_omitida` | produtos | DIN | nenhum | fixture dinamica |
| 161 | `produtos/tests/test_v11_carrossel.py::FonteBTest::test_ficha_em_fallback_por_a_expirada_nunca_tem_preco` | produtos | DIN | nenhum | fixture dinamica |
| 162 | `produtos/tests/test_v11_carrossel.py::FormatoEDeterminismoTest::test_deterministico` | produtos | DIN | nenhum | fixture dinamica |
| 163 | `produtos/tests/test_v11_carrossel.py::FormatoEDeterminismoTest::test_formato_do_gerador` | produtos | DIN | nenhum | fixture dinamica |
| 164 | `produtos/tests/test_v11_carrossel.py::FormatoEDeterminismoTest::test_funcao_pura_nao_le_relogio_nem_grava_nem_usa_rede` | produtos | DIN | nenhum | fixture dinamica |
| 165 | `produtos/tests/test_v11_carrossel.py::FormatoEDeterminismoTest::test_slides_demais_bloqueiam` | produtos | DIN | nenhum | fixture dinamica |
| 166 | `produtos/tests/test_v11_carrossel.py::ImagensTest::test_a_sem_foto_humana_nem_e_elegivel` | produtos | DIN | nenhum | fixture dinamica |
| 167 | `produtos/tests/test_v11_carrossel.py::ImagensTest::test_foto_id_obrigatoria` | produtos | DIN | nenhum | fixture dinamica |
| 168 | `produtos/tests/test_v11_carrossel.py::ImagensTest::test_foto_real_autorizada_com_hash_correto` | produtos | DIN | nenhum | fixture dinamica |
| 169 | `produtos/tests/test_v11_carrossel.py::ImagensTest::test_foto_real_exige_catalogo_provedor_real_e_aprovacao` | produtos | DIN | nenhum | fixture dinamica |
| 170 | `produtos/tests/test_v11_carrossel.py::ImagensTest::test_foto_real_nao_passa_por_ilustracao_e_pendente_e_bloqueada` | produtos | DIN | nenhum | fixture dinamica |
| 171 | `produtos/tests/test_v11_carrossel.py::ImagensTest::test_foto_real_sem_permissao_humana_ou_negada` | produtos | DIN | nenhum | fixture dinamica |
| 172 | `produtos/tests/test_v11_carrossel.py::ImagensTest::test_hash_do_catalogo_divergente` | produtos | DIN | nenhum | fixture dinamica |
| 173 | `produtos/tests/test_v11_carrossel.py::ImagensTest::test_ilustrativa_e_rotulada_nunca_como_fiel` | produtos | DIN | nenhum | fixture dinamica |
| 174 | `produtos/tests/test_v11_carrossel.py::ImagensTest::test_nunca_permite_fotos_pendentes_no_gerador` | produtos | DIN | nenhum | fixture dinamica |
| 175 | `produtos/tests/test_v11_carrossel.py::ImagensTest::test_permissao_exportada_pelo_agente_nao_basta` | produtos | DIN | nenhum | fixture dinamica |
| 176 | `produtos/tests/test_v11_carrossel.py::ImagensTest::test_sem_catalogo_a_ilustrativa_so_avisa` | produtos | DIN | nenhum | fixture dinamica |
| 177 | `produtos/tests/test_v11_carrossel.py::TitulosTest::test_risco_alta_bloqueia` | produtos | DIN | nenhum | fixture dinamica |
| 178 | `produtos/tests/test_v11_carrossel.py::TitulosTest::test_risco_media_exige_revisao_e_registra_aviso` | produtos | DIN | nenhum | fixture dinamica |
| 179 | `produtos/tests/test_v11_carrossel.py::TitulosTest::test_titulo_longo_e_abreviado_com_aviso` | produtos | DIN | nenhum | fixture dinamica |
| 180 | `produtos/tests/test_v11_conflitos_p03_p04.py::DecisoesInaplicaveisP04Test::test_b_para_publicacao` | produtos | DIN | nenhum | fixture dinamica |
| 181 | `produtos/tests/test_v11_conflitos_p03_p04.py::DecisoesInaplicaveisP04Test::test_data_futura_e_anterior_a_exportacao` | produtos | DIN | nenhum | fixture dinamica |
| 182 | `produtos/tests/test_v11_conflitos_p03_p04.py::DecisoesInaplicaveisP04Test::test_decisao_aplicada_nao_e_listada_como_inaplicavel` | produtos | DIN | nenhum | fixture dinamica |
| 183 | `produtos/tests/test_v11_conflitos_p03_p04.py::DecisoesInaplicaveisP04Test::test_decisao_de_lote_em_quarentena_fica_sem_produto` | produtos | DIN | nenhum | fixture dinamica |
| 184 | `produtos/tests/test_v11_conflitos_p03_p04.py::DecisoesInaplicaveisP04Test::test_decisao_sobre_produto_ausente_das_fontes` | produtos | DIN | nenhum | fixture dinamica |
| 185 | `produtos/tests/test_v11_conflitos_p03_p04.py::DecisoesInaplicaveisP04Test::test_decisao_superada_por_outra_mais_recente_aparece` | produtos | DIN | nenhum | fixture dinamica |
| 186 | `produtos/tests/test_v11_conflitos_p03_p04.py::DecisoesInaplicaveisP04Test::test_estado_automatico_nao_permite` | produtos | DIN | nenhum | fixture dinamica |
| 187 | `produtos/tests/test_v11_conflitos_p03_p04.py::DecisoesInaplicaveisP04Test::test_markdown_e_ficha_mostram_a_ocorrencia` | produtos | DIN | nenhum | fixture dinamica |
| 188 | `produtos/tests/test_v11_conflitos_p03_p04.py::DecisoesInaplicaveisP04Test::test_nada_e_concedido_e_todos_os_codigos_sao_conhecidos` | produtos | DIN | nenhum | fixture dinamica |
| 189 | `produtos/tests/test_v11_conflitos_p03_p04.py::DecisoesInaplicaveisP04Test::test_preco_e_identidade_mudaram` | produtos | DIN | nenhum | fixture dinamica |
| 190 | `produtos/tests/test_v11_conflitos_p03_p04.py::DecisoesInaplicaveisP04Test::test_versao_desconhecida` | produtos | DIN | nenhum | fixture dinamica |
| 191 | `produtos/tests/test_v11_conflitos_p03_p04.py::DivergenciaTest::test_aprovacao_exige_decisao_posterior_as_duas_exportacoes` | produtos | DIN | nenhum | fixture dinamica |
| 192 | `produtos/tests/test_v11_conflitos_p03_p04.py::DivergenciaTest::test_divergencia_com_b_no_fallback_tambem_exige_revisao` | produtos | DIN | nenhum | fixture dinamica |
| 193 | `produtos/tests/test_v11_conflitos_p03_p04.py::DivergenciaTest::test_divergencia_de_caracteristicas` | produtos | DIN | nenhum | fixture dinamica |
| 194 | `produtos/tests/test_v11_conflitos_p03_p04.py::DivergenciaTest::test_divergencia_de_identidade_exige_revisao` | produtos | DIN | nenhum | fixture dinamica |
| 195 | `produtos/tests/test_v11_conflitos_p03_p04.py::DivergenciaTest::test_divergencia_nao_mascara_estado_expirado_invalidado_ou_incompleto` | produtos | DIN | nenhum | fixture dinamica |
| 196 | `produtos/tests/test_v11_conflitos_p03_p04.py::DivergenciaTest::test_divergencia_nao_vaza_dado_de_b_para_a` | produtos | DIN | nenhum | fixture dinamica |
| 197 | `produtos/tests/test_v11_conflitos_p03_p04.py::PoliticaABTest::test_a_expirada_nao_autoriza_comercial_e_b_continua_como_rascunho_editorial` | produtos | DIN | nenhum | fixture dinamica |
| 198 | `produtos/tests/test_v11_conflitos_p03_p04.py::PoliticaABTest::test_a_expirada_nao_recai_em_publicacao_mesmo_com_aprovacao_previa_em_a` | produtos | DIN | nenhum | fixture dinamica |
| 199 | `produtos/tests/test_v11_conflitos_p03_p04.py::PoliticaABTest::test_a_expirada_sem_b_continua_expirado` | produtos | DIN | nenhum | fixture dinamica |
| 200 | `produtos/tests/test_v11_conflitos_p03_p04.py::PoliticaABTest::test_a_indisponivel_continua_invalidada_e_nao_recai_em_b` | produtos | DIN | nenhum | fixture dinamica |
| 201 | `produtos/tests/test_v11_conflitos_p03_p04.py::PoliticaABTest::test_a_nunca_e_substituida_por_b_mesmo_mais_recente` | produtos | DIN | nenhum | fixture dinamica |
| 202 | `produtos/tests/test_v11_conflitos_p03_p04.py::PoliticaABTest::test_a_sem_foto_humana_continua_incompleta_com_b_ao_lado` | produtos | DIN | nenhum | fixture dinamica |
| 203 | `produtos/tests/test_v11_conflitos_p03_p04.py::PoliticaABTest::test_a_valida_prevalece_e_b_fornece_dados_editoriais` | produtos | DIN | nenhum | fixture dinamica |
| 204 | `produtos/tests/test_v11_conflitos_p03_p04.py::PoliticaABTest::test_aprovacao_humana_de_b_vale_como_rascunho_quando_a_expirou` | produtos | DIN | nenhum | fixture dinamica |
| 205 | `produtos/tests/test_v11_conflitos_p03_p04.py::PoliticaABTest::test_aprovacao_sobre_versao_de_b_nao_vale_quando_a_prevalece` | produtos | DIN | nenhum | fixture dinamica |
| 206 | `produtos/tests/test_v11_conflitos_p03_p04.py::PoliticaABTest::test_b_nunca_e_aprovada_para_publicacao_no_fallback` | produtos | DIN | nenhum | fixture dinamica |
| 207 | `produtos/tests/test_v11_conflitos_p03_p04.py::PoliticaABTest::test_categoria_de_b_e_so_sugestao_visivel` | produtos | DIN | nenhum | fixture dinamica |
| 208 | `produtos/tests/test_v11_conflitos_p03_p04.py::PoliticaABTest::test_historico_guarda_as_duas_fontes` | produtos | DIN | nenhum | fixture dinamica |
| 209 | `produtos/tests/test_v11_conflitos_p03_p04.py::PoliticaABTest::test_nunca_ha_aprovacao_automatica` | produtos | DIN | nenhum | fixture dinamica |
| 210 | `produtos/tests/test_v11_conflitos_p03_p04.py::PoliticaABTest::test_permissao_de_foto_nao_e_substituida_por_nenhuma_fonte` | produtos | DIN | nenhum | fixture dinamica |
| 211 | `produtos/tests/test_v11_conflitos_p03_p04.py::PoliticaABTest::test_rejeicao_humana_vale_mesmo_sobre_a_outra_fonte` | produtos | DIN | nenhum | fixture dinamica |
| 212 | `produtos/tests/test_v11_conformidade_514a.py::BloqueiosNormaisTest::test_bloqueio_por_estado_nao_avalia_o_portao_nem_gera_slides` | produtos | DIN | nenhum | fixture dinamica |
| 213 | `produtos/tests/test_v11_conformidade_514a.py::BloqueiosNormaisTest::test_chamada_invalida_continua_sendo_excecao_de_programacao` | produtos | DIN | nenhum | fixture dinamica |
| 214 | `produtos/tests/test_v11_conformidade_514a.py::BloqueiosNormaisTest::test_lote_misto_sem_tratamento_de_excecao` | produtos | DIN | nenhum | fixture dinamica |
| 215 | `produtos/tests/test_v11_conformidade_514a.py::BloqueiosNormaisTest::test_origem_desconhecida_tambem_e_bloqueio` | produtos | DIN | nenhum | fixture dinamica |
| 216 | `produtos/tests/test_v11_conformidade_514a.py::BloqueiosNormaisTest::test_relatorio_de_bloqueio_tem_as_mesmas_chaves_do_resultado_normal` | produtos | DIN | nenhum | fixture dinamica |
| 217 | `produtos/tests/test_v11_conformidade_514a.py::DivergenciaValoresTest::test_campo_novo_e_distinto_de_valor_alterado` | produtos | DIN | nenhum | fixture dinamica |
| 218 | `produtos/tests/test_v11_conformidade_514a.py::DivergenciaValoresTest::test_caracteristicas_divergentes_valor_e_formatacao` | produtos | DIN | nenhum | fixture dinamica |
| 219 | `produtos/tests/test_v11_conformidade_514a.py::DivergenciaValoresTest::test_data_de_verificacao_e_exportid_de_b_nao_contam` | produtos | DIN | nenhum | fixture dinamica |
| 220 | `produtos/tests/test_v11_conformidade_514a.py::DivergenciaValoresTest::test_divergencia_preexistente_inalterada_nao_invalida_com_reexportacao_tecnica` | produtos | DIN | nenhum | fixture dinamica |
| 221 | `produtos/tests/test_v11_conformidade_514a.py::DivergenciaValoresTest::test_formatacao_nao_invalida` | produtos | DIN | nenhum | fixture dinamica |
| 222 | `produtos/tests/test_v11_conformidade_514a.py::DivergenciaValoresTest::test_preco_e_disponibilidade_continuam_pelo_portao_nao_pela_divergencia` | produtos | DIN | nenhum | fixture dinamica |
| 223 | `produtos/tests/test_v11_conformidade_514a.py::DivergenciaValoresTest::test_reducao_do_conjunto_de_divergencias_continua_valida` | produtos | DIN | nenhum | fixture dinamica |
| 224 | `produtos/tests/test_v11_conformidade_514a.py::DivergenciaValoresTest::test_revisada_na_fonte_b_quando_a_expirou_tambem_reconhece_mudanca_de_valor_de_a` | produtos | DIN | nenhum | fixture dinamica |
| 225 | `produtos/tests/test_v11_conformidade_514a.py::DivergenciaValoresTest::test_url_oficial_com_valor_diferente_invalida` | produtos | DIN | nenhum | fixture dinamica |
| 226 | `produtos/tests/test_v11_conformidade_514a.py::DivergenciaValoresTest::test_utilitarios_de_valor` | produtos | DIN | nenhum | fixture dinamica |
| 227 | `produtos/tests/test_v11_conformidade_514a.py::DivergenciaValoresTest::test_valor_divergente_materialmente_diferente_invalida_rascunho_e_publicacao` | produtos | DIN | nenhum | fixture dinamica |
| 228 | `produtos/tests/test_v11_conformidade_514a.py::ImpressaoEDecisoesTest::test_arquivo_de_decisoes_nunca_e_alterado` | produtos | DIN | nenhum | fixture dinamica |
| 229 | `produtos/tests/test_v11_conformidade_514a.py::ImpressaoEDecisoesTest::test_auditoria_status_do_arquivo` | produtos | DIN | nenhum | fixture dinamica |
| 230 | `produtos/tests/test_v11_conformidade_514a.py::ImpressaoEDecisoesTest::test_campo_extra_comum_e_decisao_invalida_sao_estruturados_sem_o_codigo_de_impressao` | produtos | DIN | nenhum | fixture dinamica |
| 231 | `produtos/tests/test_v11_conformidade_514a.py::ImpressaoEDecisoesTest::test_decisoes_antigas_sem_impressao_continuam_valendo` | produtos | DIN | nenhum | fixture dinamica |
| 232 | `produtos/tests/test_v11_conformidade_514a.py::ImpressaoEDecisoesTest::test_decisoes_inaplicaveis_preservadas_com_as_chaves_antigas_e_novas` | produtos | DIN | nenhum | fixture dinamica |
| 233 | `produtos/tests/test_v11_conformidade_514a.py::ImpressaoEDecisoesTest::test_formato_e_carregador_do_modo_1_0_nao_mudaram` | produtos | DIN | nenhum | fixture dinamica |
| 234 | `produtos/tests/test_v11_conformidade_514a.py::ImpressaoEDecisoesTest::test_impressao_decisao_expoe_o_que_foi_comparado` | produtos | DIN | nenhum | fixture dinamica |
| 235 | `produtos/tests/test_v11_conformidade_514a.py::ImpressaoEDecisoesTest::test_impressao_fornecida_pelo_arquivo_nunca_e_aceita_mesmo_se_correta` | produtos | DIN | nenhum | fixture dinamica |
| 236 | `produtos/tests/test_v11_conformidade_514a.py::ImpressaoEDecisoesTest::test_nomes_alternativos_de_impressao` | produtos | DIN | nenhum | fixture dinamica |
| 237 | `produtos/tests/test_v11_conformidade_514a.py::ImpressaoEDecisoesTest::test_versao_historica_indisponivel_fica_explicita_e_conservadora` | produtos | DIN | nenhum | fixture dinamica |
| 238 | `produtos/tests/test_v11_curadoria.py::AlegacoesComerciaisTest::test_fatos_com_alegacao_comercial_sao_rejeitados` | produtos | DIN | nenhum | fixture dinamica |
| 239 | `produtos/tests/test_v11_curadoria.py::AlegacoesComerciaisTest::test_fatos_com_risco_alto_nao_comercial_ou_medio_geram_aviso_sem_rejeitar` | produtos | DIN | nenhum | fixture dinamica |
| 240 | `produtos/tests/test_v11_curadoria.py::AlegacoesComerciaisTest::test_limitacoes_estao_documentadas` | produtos | DIN | nenhum | fixture dinamica |
| 241 | `produtos/tests/test_v11_curadoria.py::AlegacoesComerciaisTest::test_mensagens_nao_ecoam_o_texto_rejeitado` | produtos | DIN | nenhum | fixture dinamica |
| 242 | `produtos/tests/test_v11_curadoria.py::AlegacoesComerciaisTest::test_titulo_de_risco_alta_e_rejeitado` | produtos | DIN | nenhum | fixture dinamica |
| 243 | `produtos/tests/test_v11_curadoria.py::AlegacoesComerciaisTest::test_titulo_de_risco_media_sem_alegacao_comercial_gera_aviso` | produtos | DIN | nenhum | fixture dinamica |
| 244 | `produtos/tests/test_v11_curadoria.py::AlegacoesComerciaisTest::test_titulos_com_alegacao_comercial_sao_rejeitados` | produtos | DIN | nenhum | fixture dinamica |
| 245 | `produtos/tests/test_v11_curadoria.py::AlegacoesComerciaisTest::test_titulos_e_fatos_normais_passam` | produtos | DIN | nenhum | fixture dinamica |
| 246 | `produtos/tests/test_v11_curadoria.py::FichaEPipelineTest::test_aprovacao_editorial_vale_e_publicacao_nunca` | produtos | DIN | nenhum | fixture dinamica |
| 247 | `produtos/tests/test_v11_curadoria.py::FichaEPipelineTest::test_carrossel_editorial_da_curadoria_nao_tem_nenhuma_informacao_comercial` | produtos | DIN | nenhum | fixture dinamica |
| 248 | `produtos/tests/test_v11_curadoria.py::FichaEPipelineTest::test_curadoria_em_lote_b_com_manifesto_integro_e_lote_adulterado_em_quarentena` | produtos | DIN | nenhum | fixture dinamica |
| 249 | `produtos/tests/test_v11_curadoria.py::FichaEPipelineTest::test_exemplos_ficticios_do_1_1_continuam_iguais` | produtos | DIN | nenhum | fixture dinamica;fixture estatica |
| 250 | `produtos/tests/test_v11_curadoria.py::FichaEPipelineTest::test_ficha_sem_preco_e_candidato_nao_verificado_e_renderiza_com_seguranca` | produtos | DIN | nenhum | fixture dinamica |
| 251 | `produtos/tests/test_v11_curadoria.py::FichaEPipelineTest::test_historico_e_resumo_com_preco_nulo` | produtos | DIN | nenhum | fixture dinamica |
| 252 | `produtos/tests/test_v11_curadoria.py::FichaEPipelineTest::test_mudanca_de_nulo_para_valor_nao_quebra_a_ficha` | produtos | DIN | nenhum | fixture dinamica |
| 253 | `produtos/tests/test_v11_curadoria.py::FichaEPipelineTest::test_processamento_a_b_existente_nao_muda_com_curadoria_ao_lado` | produtos | DIN | nenhum | fixture dinamica |
| 254 | `produtos/tests/test_v11_curadoria.py::FonteTest::test_combinacao_obrigatoria_de_kind_system_provider` | produtos | DIN | nenhum | fixture dinamica |
| 255 | `produtos/tests/test_v11_curadoria.py::FonteTest::test_contrato_desconhecido_e_erro_de_programacao` | produtos | DIN | nenhum | fixture dinamica |
| 256 | `produtos/tests/test_v11_curadoria.py::FonteTest::test_curadoria_nunca_entra_em_a` | produtos | DIN | nenhum | fixture dinamica |
| 257 | `produtos/tests/test_v11_curadoria.py::FonteTest::test_curadoria_valida_no_contrato_1_1` | produtos | DIN | nenhum | fixture dinamica |
| 258 | `produtos/tests/test_v11_curadoria.py::FonteTest::test_modo_1_0_rejeita_curadoria_preco_nulo_e_identificadores` | produtos | DIN | nenhum | fixture dinamica |
| 259 | `produtos/tests/test_v11_curadoria.py::FonteTest::test_tipos_do_agente_exigem_sistema_do_agente_e_nao_usam_o_provider_reservado` | produtos | DIN | nenhum | fixture dinamica |
| 260 | `produtos/tests/test_v11_curadoria.py::FonteTest::test_validador_padrao_continua_igual_para_as_fontes_do_agente` | produtos | DIN | nenhum | fixture dinamica |
| 261 | `produtos/tests/test_v11_curadoria.py::P08Test::test_impressao_com_preco_nulo_e_deterministica` | produtos | DIN | nenhum | fixture dinamica |
| 262 | `produtos/tests/test_v11_curadoria.py::P08Test::test_mudancas_materiais_invalidam_com_o_codigo_certo` | produtos | DIN | nenhum | fixture dinamica |
| 263 | `produtos/tests/test_v11_curadoria.py::P08Test::test_reexportacao_sem_mudanca_material_mantem_a_aprovacao` | produtos | DIN | nenhum | fixture dinamica |
| 264 | `produtos/tests/test_v11_curadoria.py::PrecoNuloTest::test_com_preco_nulo_verificacao_e_validade_devem_ser_nulas` | produtos | DIN | nenhum | fixture dinamica |
| 265 | `produtos/tests/test_v11_curadoria.py::PrecoNuloTest::test_disponibilidade_obrigatoriamente_desconhecida` | produtos | DIN | nenhum | fixture dinamica |
| 266 | `produtos/tests/test_v11_curadoria.py::PrecoNuloTest::test_preco_ausente_continua_obrigatorio` | produtos | DIN | nenhum | fixture dinamica |
| 267 | `produtos/tests/test_v11_curadoria.py::PrecoNuloTest::test_preco_nao_nulo_em_curadoria_segue_as_regras_de_b` | produtos | DIN | nenhum | fixture dinamica |
| 268 | `produtos/tests/test_v11_curadoria.py::PrecoNuloTest::test_preco_nulo_e_exclusivo_da_curadoria` | produtos | DIN | nenhum | fixture dinamica |
| 269 | `produtos/tests/test_v11_curadoria.py::PrecoNuloTest::test_publicacao_e_elegibilidade_de_b_se_aplicam` | produtos | DIN | nenhum | fixture dinamica |
| 270 | `produtos/tests/test_v11_curadoria.py::PrecoNuloTest::test_tipos_de_preco_invalidos_continuam_invalidos` | produtos | DIN | nenhum | fixture dinamica |
| 271 | `produtos/tests/test_v11_curadoria.py::UrlsEFatosTest::test_cada_fato_tem_sourceref_e_data_valida_nao_futura` | produtos | DIN | nenhum | fixture dinamica |
| 272 | `produtos/tests/test_v11_curadoria.py::UrlsEFatosTest::test_janela_de_30_dias_existente_continua_valendo` | produtos | DIN | nenhum | fixture dinamica |
| 273 | `produtos/tests/test_v11_curadoria.py::UrlsEFatosTest::test_limite_de_20_fatos` | produtos | DIN | nenhum | fixture dinamica |
| 274 | `produtos/tests/test_v11_curadoria.py::UrlsEFatosTest::test_mensagens_nao_vazam_a_url` | produtos | DIN | nenhum | fixture dinamica |
| 275 | `produtos/tests/test_v11_curadoria.py::UrlsEFatosTest::test_officialurl_e_referencias` | produtos | DIN | nenhum | fixture dinamica;http negativo |
| 276 | `produtos/tests/test_v11_curadoria.py::UrlsEFatosTest::test_sourceref_https_obrigatorio_e_verificavel_pelo_nome` | produtos | DIN | nenhum | fixture dinamica;http negativo |
| 277 | `produtos/tests/test_v11_curadoria.py::UrlsEFatosTest::test_url_valida_nao_equivale_a_verificacao` | produtos | DIN | nenhum | fixture dinamica |
| 278 | `produtos/tests/test_v11_curadoria.py::UrlsEFatosTest::test_utilitarios_de_host` | produtos | DIN | nenhum | fixture dinamica |
| 279 | `produtos/tests/test_v11_leitor.py::LeitorV11Test::test_arquivo_alterado_depois_do_manifesto` | produtos | DIN | nenhum | fixture dinamica |
| 280 | `produtos/tests/test_v11_leitor.py::LeitorV11Test::test_arquivo_invalido_dentro_de_lote_integro_nao_derruba_os_outros` | produtos | DIN | nenhum | fixture dinamica |
| 281 | `produtos/tests/test_v11_leitor.py::LeitorV11Test::test_cada_pasta_exige_o_proprio_manifesto` | produtos | DIN | nenhum | fixture dinamica |
| 282 | `produtos/tests/test_v11_leitor.py::LeitorV11Test::test_fonte_na_pasta_errada_vai_para_quarentena_do_arquivo` | produtos | DIN | nenhum | fixture dinamica |
| 283 | `produtos/tests/test_v11_leitor.py::LeitorV11Test::test_inconsistencias_levam_o_lote_inteiro_a_quarentena` | produtos | DIN | nenhum | fixture dinamica |
| 284 | `produtos/tests/test_v11_leitor.py::LeitorV11Test::test_lote_integro_e_lido` | produtos | DIN | nenhum | fixture dinamica |
| 285 | `produtos/tests/test_v11_leitor.py::LeitorV11Test::test_manifesto_ilegivel_invalido_e_simbolico` | produtos | DIN | nenhum | fixture dinamica |
| 286 | `produtos/tests/test_v11_leitor.py::LeitorV11Test::test_manifesto_na_raiz_nao_vale_para_as_pastas` | produtos | DIN | nenhum | fixture dinamica |
| 287 | `produtos/tests/test_v11_leitor.py::LeitorV11Test::test_modo_1_0_continua_aceitando_ausencia_de_manifesto` | produtos | DIN | nenhum | fixture dinamica |
| 288 | `produtos/tests/test_v11_leitor.py::LeitorV11Test::test_pasta_ausente_ou_vazia_nao_e_quarentena` | produtos | DIN | nenhum | fixture dinamica |
| 289 | `produtos/tests/test_v11_leitor.py::LeitorV11Test::test_sem_manifesto_quarentena_do_lote_inteiro` | produtos | DIN | nenhum | fixture dinamica |
| 290 | `produtos/tests/test_v11_leitor.py::LeitorV11Test::test_somente_leitura_nada_na_pasta_muda` | produtos | DIN | nenhum | fixture dinamica |
| 291 | `produtos/tests/test_v11_manifesto_p01.py::LoteComManifestoEstritoTest::test_arquivos_de_origem_ficam_intactos_na_quarentena` | produtos | DIN | nenhum | fixture dinamica |
| 292 | `produtos/tests/test_v11_manifesto_p01.py::LoteComManifestoEstritoTest::test_bytes_divergente_do_conteudo_real` | produtos | DIN | nenhum | fixture dinamica |
| 293 | `produtos/tests/test_v11_manifesto_p01.py::LoteComManifestoEstritoTest::test_cada_lote_tem_o_seu_manifesto_estrito` | produtos | DIN | nenhum | fixture dinamica |
| 294 | `produtos/tests/test_v11_manifesto_p01.py::LoteComManifestoEstritoTest::test_campos_faltando_ou_invalidos_poem_o_lote_inteiro_em_quarentena` | produtos | DIN | nenhum | fixture dinamica |
| 295 | `produtos/tests/test_v11_manifesto_p01.py::LoteComManifestoEstritoTest::test_count_diverge_dos_arquivos_presentes` | produtos | DIN | nenhum | fixture dinamica |
| 296 | `produtos/tests/test_v11_manifesto_p01.py::LoteComManifestoEstritoTest::test_lote_conforme_e_lido` | produtos | DIN | nenhum | fixture dinamica |
| 297 | `produtos/tests/test_v11_manifesto_p01.py::LoteComManifestoEstritoTest::test_manifesto_do_formato_antigo_e_recusado_no_1_1_mas_aceito_no_1_0` | produtos | DIN | nenhum | fixture dinamica |
| 298 | `produtos/tests/test_v11_manifesto_p01.py::LoteComManifestoEstritoTest::test_pipeline_registra_quarentena_do_lote_com_motivo_do_formato` | produtos | DIN | nenhum | fixture dinamica |
| 299 | `produtos/tests/test_v11_manifesto_p01.py::LoteComManifestoEstritoTest::test_sha_e_bytes_divergentes_sao_reportados_juntos` | produtos | DIN | nenhum | fixture dinamica |
| 300 | `produtos/tests/test_v11_manifesto_p01.py::ManifestoEstritoTest::test_cada_campo_obrigatorio_ausente` | produtos | DIN | nenhum | fixture dinamica |
| 301 | `produtos/tests/test_v11_manifesto_p01.py::ManifestoEstritoTest::test_campos_desconhecidos_em_qualquer_nivel` | produtos | DIN | nenhum | fixture dinamica |
| 302 | `produtos/tests/test_v11_manifesto_p01.py::ManifestoEstritoTest::test_count` | produtos | DIN | nenhum | fixture dinamica |
| 303 | `produtos/tests/test_v11_manifesto_p01.py::ManifestoEstritoTest::test_files_e_itens` | produtos | DIN | nenhum | fixture dinamica |
| 304 | `produtos/tests/test_v11_manifesto_p01.py::ManifestoEstritoTest::test_formato_estrutural` | produtos | DIN | nenhum | fixture dinamica |
| 305 | `produtos/tests/test_v11_manifesto_p01.py::ManifestoEstritoTest::test_generated_at` | produtos | DIN | nenhum | fixture dinamica |
| 306 | `produtos/tests/test_v11_manifesto_p01.py::ManifestoEstritoTest::test_generated_at_futuro_com_tolerancia` | produtos | DIN | nenhum | fixture dinamica |
| 307 | `produtos/tests/test_v11_manifesto_p01.py::ManifestoEstritoTest::test_manifest_version` | produtos | DIN | nenhum | fixture dinamica |
| 308 | `produtos/tests/test_v11_manifesto_p01.py::ManifestoEstritoTest::test_manifesto_valido` | produtos | DIN | nenhum | fixture dinamica |
| 309 | `produtos/tests/test_v11_manifesto_p01.py::ManifestoEstritoTest::test_mensagens_nao_vazam_valores` | produtos | DIN | nenhum | fixture dinamica |
| 310 | `produtos/tests/test_v11_manifesto_p01.py::ManifestoEstritoTest::test_nome_duplicado` | produtos | DIN | nenhum | fixture dinamica |
| 311 | `produtos/tests/test_v11_manifesto_p01.py::ManifestoEstritoTest::test_nomes_invalidos` | produtos | DIN | nenhum | fixture dinamica |
| 312 | `produtos/tests/test_v11_manifesto_p01.py::ManifestoEstritoTest::test_sha256_e_bytes` | produtos | DIN | nenhum | fixture dinamica |
| 313 | `produtos/tests/test_v11_p08.py::AprovacaoNaoEValidadeComercialTest::test_aprovacao_de_publicacao_nao_estende_a_janela_de_24h` | produtos | DIN | nenhum | fixture dinamica |
| 314 | `produtos/tests/test_v11_p08.py::AprovacaoNaoEValidadeComercialTest::test_portao_continua_bloqueando_fora_da_janela_mesmo_com_aprovacao_e_sem_mudanca_material` | produtos | DIN | nenhum | fixture dinamica |
| 315 | `produtos/tests/test_v11_p08.py::CamposMateriaisTest::test_aprovacao_invalidada_volta_ao_estado_automatico_nunca_a_aprovado` | produtos | DIN | nenhum | fixture dinamica |
| 316 | `produtos/tests/test_v11_p08.py::CamposMateriaisTest::test_codigos_novos_estao_no_vocabulario` | produtos | DIN | nenhum | fixture dinamica |
| 317 | `produtos/tests/test_v11_p08.py::CamposMateriaisTest::test_disponibilidade_so_invalida_publicacao` | produtos | DIN | nenhum | fixture dinamica |
| 318 | `produtos/tests/test_v11_p08.py::CamposMateriaisTest::test_fatos_mudaram_invalida_ambos_os_tipos` | produtos | DIN | nenhum | fixture dinamica |
| 319 | `produtos/tests/test_v11_p08.py::CamposMateriaisTest::test_fonte_de_comprovacao_mudou_com_o_mesmo_fato` | produtos | DIN | nenhum | fixture dinamica |
| 320 | `produtos/tests/test_v11_p08.py::CamposMateriaisTest::test_fonte_mudou_em_b` | produtos | DIN | nenhum | fixture dinamica |
| 321 | `produtos/tests/test_v11_p08.py::CamposMateriaisTest::test_identidade_invalida_rascunho_e_publicacao` | produtos | DIN | nenhum | fixture dinamica |
| 322 | `produtos/tests/test_v11_p08.py::CamposMateriaisTest::test_preco_so_invalida_publicacao_nunca_o_rascunho` | produtos | DIN | nenhum | fixture dinamica |
| 323 | `produtos/tests/test_v11_p08.py::CamposMateriaisTest::test_so_a_data_de_verificacao_do_fato_mudar_nao_invalida` | produtos | DIN | nenhum | fixture dinamica |
| 324 | `produtos/tests/test_v11_p08.py::CamposMateriaisTest::test_varias_mudancas_listam_todos_os_codigos_na_ordem_fixa` | produtos | DIN | nenhum | fixture dinamica |
| 325 | `produtos/tests/test_v11_p08.py::DecisoesAntigasTest::test_campo_impressao_no_arquivo_de_decisoes_nao_e_aceito_e_fica_visivel` | produtos | DIN | nenhum | fixture dinamica |
| 326 | `produtos/tests/test_v11_p08.py::DecisoesAntigasTest::test_decisao_anterior_a_exportacao_revisada_continua_inaplicavel` | produtos | DIN | nenhum | fixture dinamica |
| 327 | `produtos/tests/test_v11_p08.py::DecisoesAntigasTest::test_decisao_antiga_sem_impressao_continua_valida_quando_a_versao_revisada_existe` | produtos | DIN | nenhum | fixture dinamica |
| 328 | `produtos/tests/test_v11_p08.py::DecisoesAntigasTest::test_decisao_sem_versao_revisada_nas_fontes_e_tratada_de_forma_explicita_e_conservadora` | produtos | DIN | nenhum | fixture dinamica |
| 329 | `produtos/tests/test_v11_p08.py::DecisoesAntigasTest::test_formato_do_arquivo_de_decisoes_nao_mudou` | produtos | DIN | nenhum | fixture dinamica |
| 330 | `produtos/tests/test_v11_p08.py::DeterminismoTest::test_componentes_por_tipo` | produtos | DIN | nenhum | fixture dinamica |
| 331 | `produtos/tests/test_v11_p08.py::DeterminismoTest::test_divergencias_utilitarios` | produtos | DIN | nenhum | fixture dinamica |
| 332 | `produtos/tests/test_v11_p08.py::DeterminismoTest::test_impressao_e_sha256_estavel` | produtos | DIN | nenhum | fixture dinamica |
| 333 | `produtos/tests/test_v11_p08.py::DeterminismoTest::test_independente_da_ordem_de_campos_e_listas_e_da_caixa_do_texto` | produtos | DIN | nenhum | fixture dinamica |
| 334 | `produtos/tests/test_v11_p08.py::DeterminismoTest::test_muda_quando_algo_material_muda_e_e_especifica_por_tipo` | produtos | DIN | nenhum | fixture dinamica |
| 335 | `produtos/tests/test_v11_p08.py::DeterminismoTest::test_rejeicao_nao_tem_impressao` | produtos | DIN | nenhum | fixture dinamica |
| 336 | `produtos/tests/test_v11_p08.py::DivergenciaABTest::test_aprovacao_com_divergencia_na_revisao_vale_para_b_tambem` | produtos | DIN | nenhum | fixture dinamica |
| 337 | `produtos/tests/test_v11_p08.py::DivergenciaABTest::test_b_que_aparece_depois_da_decisao_com_divergencia_invalida_e_sem_divergencia_mantem` | produtos | DIN | nenhum | fixture dinamica |
| 338 | `produtos/tests/test_v11_p08.py::DivergenciaABTest::test_campo_novo_divergente_invalida` | produtos | DIN | nenhum | fixture dinamica |
| 339 | `produtos/tests/test_v11_p08.py::DivergenciaABTest::test_divergencia_inalterada_mantem_mesmo_com_reexportacoes` | produtos | DIN | nenhum | fixture dinamica |
| 340 | `produtos/tests/test_v11_p08.py::DivergenciaABTest::test_divergencia_que_diminui_mantem` | produtos | DIN | nenhum | fixture dinamica |
| 341 | `produtos/tests/test_v11_p08.py::DivergenciaABTest::test_fatos_divergentes_novos_invalidam` | produtos | DIN | nenhum | fixture dinamica |
| 342 | `produtos/tests/test_v11_p08.py::DivergenciaABTest::test_mesmo_campo_divergente_com_valor_materialmente_diferente_invalida` | produtos | DIN | nenhum | fixture dinamica |
| 343 | `produtos/tests/test_v11_p08.py::PreservacaoTest::test_arquivos_de_decisoes_e_exportacoes_nao_sao_alterados` | produtos | DIN | nenhum | fixture dinamica |
| 344 | `produtos/tests/test_v11_p08.py::PreservacaoTest::test_decisoes_inaplicaveis_antigas_continuam_com_os_mesmos_codigos` | produtos | DIN | nenhum | fixture dinamica |
| 345 | `produtos/tests/test_v11_p08.py::PreservacaoTest::test_historico_preserva_as_duas_versoes` | produtos | DIN | nenhum | fixture dinamica |
| 346 | `produtos/tests/test_v11_p08.py::PreservacaoTest::test_resumo_lista_a_invalidacao_material` | produtos | DIN | nenhum | fixture dinamica |
| 347 | `produtos/tests/test_v11_p08.py::ReexportacaoSemMudancaTest::test_metadados_nao_entram_na_impressao` | produtos | DIN | nenhum | fixture dinamica |
| 348 | `produtos/tests/test_v11_p08.py::ReexportacaoSemMudancaTest::test_nova_exportacao_sem_mudanca_material_mantem_a_aprovacao` | produtos | DIN | nenhum | fixture dinamica |
| 349 | `produtos/tests/test_v11_p08.py::ReexportacaoSemMudancaTest::test_reexportacao_b_sem_mudanca_mantem_rascunho` | produtos | DIN | nenhum | fixture dinamica |
| 350 | `produtos/tests/test_v11_p08.py::ReexportacaoSemMudancaTest::test_reexportacao_posterior_a_decisao_tambem_mantem` | produtos | DIN | nenhum | fixture dinamica |
| 351 | `produtos/tests/test_v11_permissoes.py::PermissoesTest::test_arquivo_grande_ou_tipo_invalido` | produtos | DIN | nenhum | fixture dinamica |
| 352 | `produtos/tests/test_v11_permissoes.py::PermissoesTest::test_arquivo_humano_ausente_nao_concede_nada` | produtos | DIN | nenhum | fixture dinamica |
| 353 | `produtos/tests/test_v11_permissoes.py::PermissoesTest::test_autor_de_automacao_e_registro_invalido_sao_ignorados` | produtos | DIN | nenhum | fixture dinamica |
| 354 | `produtos/tests/test_v11_permissoes.py::PermissoesTest::test_caminho_feliz` | produtos | DIN | nenhum | fixture dinamica |
| 355 | `produtos/tests/test_v11_permissoes.py::PermissoesTest::test_evidencia_ausente_ou_adulterada_ou_com_caminho_perigoso` | produtos | DIN | nenhum | fixture dinamica |
| 356 | `produtos/tests/test_v11_permissoes.py::PermissoesTest::test_evidencia_nao_pode_ser_a_url_da_foto_do_agente` | produtos | DIN | nenhum | fixture dinamica |
| 357 | `produtos/tests/test_v11_permissoes.py::PermissoesTest::test_foto_simbolica_e_recusada` | produtos | DIN | nenhum | fixture dinamica |
| 358 | `produtos/tests/test_v11_permissoes.py::PermissoesTest::test_hash_divergente_ou_arquivo_renomeado` | produtos | DIN | nenhum | fixture dinamica |
| 359 | `produtos/tests/test_v11_permissoes.py::PermissoesTest::test_leitura_nunca_grava` | produtos | DIN | nenhum | fixture dinamica |
| 360 | `produtos/tests/test_v11_permissoes.py::PermissoesTest::test_negada_posterior_revoga_confirmada` | produtos | DIN | nenhum | fixture dinamica |
| 361 | `produtos/tests/test_v11_permissoes.py::PermissoesTest::test_politica_de_arquivo_de_foto` | produtos | DIN | nenhum | fixture dinamica |
| 362 | `produtos/tests/test_v11_permissoes.py::PermissoesTest::test_schema_version_errado_ou_json_invalido_nao_concede_nada` | produtos | DIN | nenhum | fixture dinamica |
| 363 | `produtos/tests/test_v11_permissoes.py::PermissoesTest::test_sem_registro_ou_sem_repositorio_de_fotos` | produtos | DIN | nenhum | fixture dinamica |
| 364 | `produtos/tests/test_v11_permissoes.py::PermissoesTest::test_termo_inexistente_e_escopo_errado` | produtos | DIN | nenhum | fixture dinamica |
| 365 | `produtos/tests/test_v11_pipeline.py::CliV11Test::test_cli_1_1` | produtos | OP | baixo/central | fixture dinamica;fixture estatica;entrada operacional |
| 366 | `produtos/tests/test_v11_pipeline.py::CliV11Test::test_cli_1_1_com_saida_dentro_da_entrada_e_recusada` | produtos | OP | baixo/central | fixture dinamica;fixture estatica;entrada operacional |
| 367 | `produtos/tests/test_v11_pipeline.py::CliV11Test::test_cli_1_1_exige_dados_e_recusa_janela_maior_que_24h` | produtos | OP | baixo/central | fixture dinamica;fixture estatica;entrada operacional |
| 368 | `produtos/tests/test_v11_pipeline.py::ExemploCompletoTest::test_commits_invalidos_sao_recusados` | produtos | DIN | nenhum | fixture dinamica |
| 369 | `produtos/tests/test_v11_pipeline.py::ExemploCompletoTest::test_configuracao_do_modo_1_0_nao_e_aceita_no_modo_1_1` | produtos | DIN | nenhum | fixture dinamica;fixture estatica |
| 370 | `produtos/tests/test_v11_pipeline.py::ExemploCompletoTest::test_exemplo_fictício_completo` | produtos | DIN | nenhum | fixture dinamica;fixture estatica |
| 371 | `produtos/tests/test_v11_pipeline.py::ExemploCompletoTest::test_ficha_a_com_foto_humana_e_b_sem_preco` | produtos | DIN | nenhum | fixture dinamica;fixture estatica |
| 372 | `produtos/tests/test_v11_pipeline.py::ExemploCompletoTest::test_lote_sem_manifesto_nao_gera_fichas_e_aparece_no_relatorio` | produtos | DIN | nenhum | fixture dinamica |
| 373 | `produtos/tests/test_v11_pipeline.py::ExemploCompletoTest::test_saida_dentro_ou_acima_de_qualquer_entrada_e_recusada` | produtos | DIN | nenhum | fixture dinamica |
| 374 | `produtos/tests/test_v11_pipeline.py::ExemploCompletoTest::test_saida_so_na_pasta_de_saida_e_deterministica` | produtos | DIN | nenhum | fixture dinamica;fixture estatica |
| 375 | `produtos/tests/test_v11_pipeline.py::ExemploCompletoTest::test_sem_arquivos_humanos_nada_e_aprovado_nem_ha_foto` | produtos | DIN | nenhum | fixture dinamica |
| 376 | `produtos/tests/test_v11_pipeline.py::FragmentoV11Test::test_b_sem_foto_autorizada_nao_gera_fragmento` | produtos | DIN | nenhum | fixture dinamica;fixture estatica |
| 377 | `produtos/tests/test_v11_pipeline.py::FragmentoV11Test::test_fragmento_com_hash_confere_e_licenca_vem_do_termo` | produtos | DIN | nenhum | fixture dinamica;fixture estatica |
| 378 | `produtos/tests/test_v11_pipeline.py::FragmentoV11Test::test_hash_do_arquivo_local_diverge` | produtos | DIN | nenhum | fixture dinamica;fixture estatica |
| 379 | `produtos/tests/test_v11_pipeline.py::FragmentoV11Test::test_recusas` | produtos | DIN | nenhum | fixture dinamica;fixture estatica |
| 380 | `produtos/tests/test_v11_pipeline.py::GarantiasEstaticasV11Test::test_arquivos_do_modo_1_0_nao_foram_reescritos` | produtos | DIN | nenhum | fixture dinamica |
| 381 | `produtos/tests/test_v11_pipeline.py::GarantiasEstaticasV11Test::test_modulos_de_leitura_nao_escrevem_nem_apagam` | produtos | DIN | nenhum | fixture dinamica |
| 382 | `produtos/tests/test_v11_pipeline.py::GarantiasEstaticasV11Test::test_novos_modulos_sem_rede_ambiente_ou_termos_proibidos` | produtos | DIN | nenhum | fixture dinamica |
| 383 | `produtos/tests/test_v11_prepublicacao_titulos.py::PortaoTest::test_agendamento_avalia_o_horario_efetivo_e_deve_ser_reavaliado` | produtos | INT | nenhum | — |
| 384 | `produtos/tests/test_v11_prepublicacao_titulos.py::PortaoTest::test_alegacao_acessoria_e_omitida_se_ha_variante_e_bloqueada_se_nao_ha` | produtos | INT | nenhum | — |
| 385 | `produtos/tests/test_v11_prepublicacao_titulos.py::PortaoTest::test_condicoes_de_falha` | produtos | INT | nenhum | — |
| 386 | `produtos/tests/test_v11_prepublicacao_titulos.py::PortaoTest::test_entradas_invalidas` | produtos | INT | nenhum | — |
| 387 | `produtos/tests/test_v11_prepublicacao_titulos.py::PortaoTest::test_essencial_bloqueia_mesmo_com_acessoria_omissivel` | produtos | INT | nenhum | — |
| 388 | `produtos/tests/test_v11_prepublicacao_titulos.py::PortaoTest::test_funcao_pura_nao_altera_a_ficha` | produtos | INT | nenhum | — |
| 389 | `produtos/tests/test_v11_prepublicacao_titulos.py::PortaoTest::test_liberar_publicacao_imediata_dentro_da_janela` | produtos | INT | nenhum | — |
| 390 | `produtos/tests/test_v11_prepublicacao_titulos.py::PortaoTest::test_margem_e_limite_inclusivo` | produtos | INT | nenhum | — |
| 391 | `produtos/tests/test_v11_prepublicacao_titulos.py::PortaoTest::test_menor_preco_exige_prova_explicita` | produtos | INT | nenhum | — |
| 392 | `produtos/tests/test_v11_prepublicacao_titulos.py::PortaoTest::test_sem_alegacao_comercial_libera_vazio` | produtos | INT | nenhum | — |
| 393 | `produtos/tests/test_v11_prepublicacao_titulos.py::PortaoTest::test_teto_de_24h_vale_mesmo_com_validuntil_maior` | produtos | INT | nenhum | — |
| 394 | `produtos/tests/test_v11_prepublicacao_titulos.py::TitulosTest::test_alta_prevalece_sobre_media_e_nao_ha_falso_positivo_de_palavra_parcial` | produtos | INT | nenhum | — |
| 395 | `produtos/tests/test_v11_prepublicacao_titulos.py::TitulosTest::test_identificacao_na_peca` | produtos | INT | nenhum | — |
| 396 | `produtos/tests/test_v11_prepublicacao_titulos.py::TitulosTest::test_niveis` | produtos | INT | nenhum | — |
| 397 | `produtos/tests/test_v11_prepublicacao_titulos.py::TitulosTest::test_titulo_nunca_e_editado` | produtos | INT | nenhum | — |
| 398 | `produtos/tests/test_v11_selecao_contrato_p02.py::CliP02Test::test_cli_1_0_atual_continua_igual_com_e_sem_legado` | produtos | OP | baixo/central | fixture estatica;entrada operacional |
| 399 | `produtos/tests/test_v11_selecao_contrato_p02.py::CliP02Test::test_dados_reais_sem_contrato_ou_1_0_sem_legado_sao_recusados` | produtos | OP | baixo/central | entrada operacional |
| 400 | `produtos/tests/test_v11_selecao_contrato_p02.py::CliP02Test::test_legado_com_1_1_e_recusado` | produtos | OP | baixo/central | entrada operacional |
| 401 | `produtos/tests/test_v11_selecao_contrato_p02.py::CliP02Test::test_selecao_valida_ainda_nao_processa_dados_reais` | produtos | OP | baixo/central | entrada operacional |
| 402 | `produtos/tests/test_v11_selecao_contrato_p02.py::SelecaoTest::test_contrato_1_0_com_dados_reais_exige_legado` | produtos | INT | nenhum | — |
| 403 | `produtos/tests/test_v11_selecao_contrato_p02.py::SelecaoTest::test_contrato_1_1_com_dados_reais_e_valido_e_legado_nao_combina_com_1_1` | produtos | INT | nenhum | — |
| 404 | `produtos/tests/test_v11_selecao_contrato_p02.py::SelecaoTest::test_contrato_desconhecido` | produtos | INT | nenhum | — |
| 405 | `produtos/tests/test_v11_selecao_contrato_p02.py::SelecaoTest::test_dados_reais_exigem_contrato_sem_padrao` | produtos | INT | nenhum | — |
| 406 | `produtos/tests/test_v11_selecao_contrato_p02.py::SelecaoTest::test_fora_de_dados_reais_nada_muda` | produtos | INT | nenhum | — |
| 407 | `produtos/tests/test_v11_selecao_contrato_p02.py::SelecaoTest::test_processamento_real_esta_desabilitado_nesta_etapa` | produtos | INT | nenhum | guarda estatica ou golden ou flags |
| 408 | `produtos/tests/test_v11_separacao_contratos.py::FonteCuradoriaNoModo10Test::test_leitor_do_modo_1_0_rejeita_o_arquivo_de_curadoria` | produtos | DIN | nenhum | fixture dinamica |
| 409 | `produtos/tests/test_v11_separacao_contratos.py::FonteCuradoriaNoModo10Test::test_modo_1_0_continua_rejeitando_a_fonte_curadoria_manual` | produtos | INT | nenhum | — |
| 410 | `produtos/tests/test_v11_separacao_contratos.py::FonteCuradoriaNoModo10Test::test_modo_1_0_rejeita_cada_elemento_da_curadoria_isoladamente` | produtos | INT | nenhum | — |
| 411 | `produtos/tests/test_v11_separacao_contratos.py::FonteCuradoriaNoModo10Test::test_modo_1_0_rejeita_curadoria_com_provider_reservado_pela_fonte_e_nao_pelo_nome` | produtos | INT | nenhum | — |
| 412 | `produtos/tests/test_v11_separacao_contratos.py::ProviderCuradoriaTest::test_contrato_1_1_reserva_o_provider_exclusivamente_para_a_curadoria_manual` | produtos | INT | nenhum | — |
| 413 | `produtos/tests/test_v11_separacao_contratos.py::ProviderCuradoriaTest::test_curadoria_manual_exige_o_provider_reservado_no_1_1` | produtos | INT | nenhum | — |
| 414 | `produtos/tests/test_v11_separacao_contratos.py::ProviderCuradoriaTest::test_leitor_1_1_recusa_fonte_do_agente_com_provider_reservado` | produtos | DIN | nenhum | fixture dinamica |
| 415 | `produtos/tests/test_v11_separacao_contratos.py::ProviderCuradoriaTest::test_modo_1_0_continua_aceitando_provider_curadoria_nas_fontes_do_agente` | produtos | INT | nenhum | — |
| 416 | `produtos/tests/test_v11_separacao_contratos.py::ProviderCuradoriaTest::test_pipeline_e_leitor_do_modo_1_0_processam_provider_curadoria` | produtos | DIN | nenhum | fixture dinamica |
| 417 | `produtos/tests/test_v11_separacao_contratos.py::ProviderCuradoriaTest::test_resultado_do_1_0_e_identico_ao_de_outro_provedor_exceto_o_nome` | produtos | INT | nenhum | — |
| 418 | `curadoria_b/tests/test_bloqueios_cli.py::BloqueiosCliTest::test_cli_da_curadoria_nao_tem_opcao_para_habilitar_nada` | curadoria_b | OP | baixo/central | fixture estatica;entrada operacional |
| 419 | `curadoria_b/tests/test_bloqueios_cli.py::BloqueiosCliTest::test_cli_recusa_dominio_real_e_nao_cria_lote` | curadoria_b | OP | baixo/central | fixture dinamica;fixture estatica;entrada operacional |
| 420 | `curadoria_b/tests/test_bloqueios_cli.py::BloqueiosCliTest::test_constantes_de_bloqueio_continuam_desabilitadas` | curadoria_b | INT | nenhum | guarda estatica ou golden ou flags |
| 421 | `curadoria_b/tests/test_bloqueios_cli.py::BloqueiosCliTest::test_exportador_nao_importa_nem_altera_a_selecao_de_dados_reais` | curadoria_b | INT | nenhum | — |
| 422 | `curadoria_b/tests/test_bloqueios_cli.py::BloqueiosCliTest::test_funcao_exportar_tambem_aplica_o_bloqueio` | curadoria_b | OP | baixo/central | fixture dinamica;fixture estatica;entrada operacional |
| 423 | `curadoria_b/tests/test_bloqueios_cli.py::BloqueiosCliTest::test_modulos_nao_leem_ambiente_nem_arquivo_de_configuracao` | curadoria_b | INT | nenhum | — |
| 424 | `curadoria_b/tests/test_bloqueios_cli.py::BloqueiosCliTest::test_receptor_continua_recusando_dados_reais_mesmo_com_lote_da_curadoria` | curadoria_b | OP | baixo/central | fixture estatica;entrada operacional |
| 425 | `curadoria_b/tests/test_bloqueios_cli.py::BloqueiosCliTest::test_variaveis_de_ambiente_nao_contornam_o_bloqueio` | curadoria_b | OP | baixo/central | fixture dinamica;fixture estatica;entrada operacional |
| 426 | `curadoria_b/tests/test_curadoria_b.py::CliTest::test_cli_erros` | curadoria_b | OP | baixo/central | fixture dinamica;fixture estatica;entrada operacional |
| 427 | `curadoria_b/tests/test_curadoria_b.py::CliTest::test_cli_sucesso` | curadoria_b | OP | baixo/central | fixture estatica;entrada operacional |
| 428 | `curadoria_b/tests/test_curadoria_b.py::FichaInvalidaTest::test_alegacoes_comerciais_e_titulo_alta` | curadoria_b | OP | baixo/central | fixture dinamica;fixture estatica;entrada operacional |
| 429 | `curadoria_b/tests/test_curadoria_b.py::FichaInvalidaTest::test_campos_comerciais_proibidos_na_entrada_humana` | curadoria_b | OP | baixo/central | fixture dinamica;fixture estatica;entrada operacional |
| 430 | `curadoria_b/tests/test_curadoria_b.py::FichaInvalidaTest::test_campos_desconhecidos_em_todos_os_niveis` | curadoria_b | OP | baixo/central | fixture dinamica;fixture estatica;entrada operacional |
| 431 | `curadoria_b/tests/test_curadoria_b.py::FichaInvalidaTest::test_campos_obrigatorios_ausentes` | curadoria_b | OP | baixo/central | fixture dinamica;fixture estatica;entrada operacional |
| 432 | `curadoria_b/tests/test_curadoria_b.py::FichaInvalidaTest::test_dados_incompletos_e_tipos` | curadoria_b | OP | baixo/central | fixture dinamica;fixture estatica;entrada operacional |
| 433 | `curadoria_b/tests/test_curadoria_b.py::FichaInvalidaTest::test_fato_com_data_futura_ou_invalida` | curadoria_b | OP | baixo/central | fixture dinamica;fixture estatica;entrada operacional |
| 434 | `curadoria_b/tests/test_curadoria_b.py::FichaInvalidaTest::test_links_inadequados` | curadoria_b | OP | baixo/central | fixture dinamica;fixture estatica;entrada operacional;http negativo |
| 435 | `curadoria_b/tests/test_curadoria_b.py::FichaInvalidaTest::test_mensagens_nao_ecoam_valores` | curadoria_b | OP | baixo/central | fixture dinamica;fixture estatica;entrada operacional |
| 436 | `curadoria_b/tests/test_curadoria_b.py::FichaValidaTest::test_categoria_opcional` | curadoria_b | OP | baixo/central | fixture dinamica;fixture estatica;entrada operacional |
| 437 | `curadoria_b/tests/test_curadoria_b.py::FichaValidaTest::test_compativel_com_o_receptor_1_1_e_preserva_candidato_nao_verificado` | curadoria_b | OP | baixo/central | fixture dinamica;fixture estatica;entrada operacional |
| 438 | `curadoria_b/tests/test_curadoria_b.py::FichaValidaTest::test_exemplo_ficticio_exporta_lote_integro` | curadoria_b | OP | baixo/central | fixture dinamica;fixture estatica;entrada operacional |
| 439 | `curadoria_b/tests/test_curadoria_b.py::FichaValidaTest::test_export_id_padrao_e_uuid_e_invalido_e_recusado` | curadoria_b | OP | baixo/central | fixture dinamica;fixture estatica;entrada operacional |
| 440 | `curadoria_b/tests/test_curadoria_b.py::FichaValidaTest::test_manifesto_estrito_e_integro` | curadoria_b | OP | baixo/central | fixture dinamica;fixture estatica;entrada operacional |
| 441 | `curadoria_b/tests/test_curadoria_b.py::FichaValidaTest::test_modo_1_0_rejeita_o_lote_exportado` | curadoria_b | OP | baixo/central | fixture dinamica;fixture estatica;entrada operacional |
| 442 | `curadoria_b/tests/test_curadoria_b.py::FichaValidaTest::test_objeto_exportado_segue_o_contrato_1_1` | curadoria_b | OP | baixo/central | fixture dinamica;fixture estatica;entrada operacional |
| 443 | `curadoria_b/tests/test_curadoria_b.py::FichaValidaTest::test_reexportacao_deterministica` | curadoria_b | OP | baixo/central | fixture dinamica;fixture estatica;entrada operacional |
| 444 | `curadoria_b/tests/test_curadoria_b.py::IntegridadeTest::test_b_existente_nunca_e_sobrescrito` | curadoria_b | OP | baixo/central | fixture dinamica;fixture estatica;entrada operacional |
| 445 | `curadoria_b/tests/test_curadoria_b.py::IntegridadeTest::test_construir_lote_e_puro` | curadoria_b | EST | nenhum | fixture estatica |
| 446 | `curadoria_b/tests/test_curadoria_b.py::IntegridadeTest::test_falha_na_validacao_nao_deixa_lote_parcial_e_limpa_so_o_que_criou` | curadoria_b | OP | baixo/central | fixture dinamica;fixture estatica;entrada operacional |
| 447 | `curadoria_b/tests/test_curadoria_b.py::IntegridadeTest::test_ficha_original_nunca_e_alterada` | curadoria_b | OP | baixo/central | fixture dinamica;fixture estatica;entrada operacional |
| 448 | `curadoria_b/tests/test_curadoria_b.py::IntegridadeTest::test_manifesto_ou_produto_adulterado_vai_para_quarentena` | curadoria_b | OP | baixo/central | fixture dinamica;fixture estatica;entrada operacional |
| 449 | `curadoria_b/tests/test_curadoria_b.py::IntegridadeTest::test_preparo_preexistente_nao_e_apagado` | curadoria_b | OP | baixo/central | fixture dinamica;fixture estatica;entrada operacional |
| 450 | `curadoria_b/tests/test_curadoria_b.py::IntegridadeTest::test_receptor_que_recusa_o_lote_levanta_e_limpa` | curadoria_b | OP | baixo/central | fixture dinamica;fixture estatica;entrada operacional |
| 451 | `curadoria_b/tests/test_curadoria_b.py::ProdutosReaisTest::test_a_chave_realmente_governa_o_bloqueio` | curadoria_b | EST | nenhum | fixture estatica;guarda estatica ou golden ou flags |
| 452 | `curadoria_b/tests/test_curadoria_b.py::ProdutosReaisTest::test_bloqueios_continuam_desabilitados` | curadoria_b | INT | nenhum | guarda estatica ou golden ou flags |
| 453 | `curadoria_b/tests/test_curadoria_b.py::ProdutosReaisTest::test_dominios_com_aparencia_de_comercio_real_sao_rejeitados_sem_rede` | curadoria_b | OP | baixo/central | fixture dinamica;fixture estatica;entrada operacional |
| 454 | `curadoria_b/tests/test_curadoria_b.py::ProdutosReaisTest::test_dominios_reservados_aceitos` | curadoria_b | OP | baixo/central | fixture dinamica;fixture estatica;entrada operacional |
| 455 | `curadoria_b/tests/test_curadoria_b.py::SemRedeTest::test_exportacao_completa_roda_com_a_rede_bloqueada` | curadoria_b | OP | baixo/central | fixture dinamica;fixture estatica;entrada operacional |
| 456 | `curadoria_b/tests/test_curadoria_b.py::SemRedeTest::test_nenhum_modulo_usa_rede_processos_ou_ambiente` | curadoria_b | INT | nenhum | — |
| 457 | `orquestrador_b2/tests/test_estilo_v2.py::Fixtures::test_aprovacao_restrita_ao_catalogo_temporario` | orquestrador_b2 | EST | nenhum | fixture estatica |
| 458 | `orquestrador_b2/tests/test_estilo_v2.py::Fixtures::test_fixtures_so_com_dados_ficticios` | orquestrador_b2 | EST | nenhum | fixture estatica |
| 459 | `orquestrador_b2/tests/test_estilo_v2.py::Fixtures::test_reconhecimento_por_conteudo` | orquestrador_b2 | EST | nenhum | fixture estatica |
| 460 | `orquestrador_b2/tests/test_estilo_v2.py::Fixtures::test_tres_fixtures_batem_com_o_hash_canonico` | orquestrador_b2 | EST | nenhum | fixture estatica |
| 461 | `orquestrador_b2/tests/test_estilo_v2.py::Fluxo::test_aprovacao_recusada_para_ficha_alterada` | orquestrador_b2 | OP | baixo/central | fixture dinamica;fixture estatica;entrada operacional |
| 462 | `orquestrador_b2/tests/test_estilo_v2.py::Fluxo::test_arquivos_da_entrega` | orquestrador_b2 | OP | adaptar | entrada operacional |
| 463 | `orquestrador_b2/tests/test_estilo_v2.py::Fluxo::test_capas_e_destaques_preservados` | orquestrador_b2 | OP | adaptar | entrada operacional |
| 464 | `orquestrador_b2/tests/test_estilo_v2.py::Fluxo::test_catalogo_do_repositorio_intacto` | orquestrador_b2 | OP | adaptar | entrada operacional |
| 465 | `orquestrador_b2/tests/test_estilo_v2.py::Fluxo::test_cli_estilo` | orquestrador_b2 | OP | baixo/central | fixture estatica;entrada operacional |
| 466 | `orquestrador_b2/tests/test_estilo_v2.py::Fluxo::test_estilo_invalido` | orquestrador_b2 | OP | baixo/central | fixture estatica;entrada operacional |
| 467 | `orquestrador_b2/tests/test_estilo_v2.py::Fluxo::test_estilo_v1_reproduz_a_b2` | orquestrador_b2 | OP | baixo/central | fixture estatica;entrada operacional |
| 468 | `orquestrador_b2/tests/test_estilo_v2.py::Fluxo::test_layouts_vizinhos_diferentes_e_fundos_nao_repetidos` | orquestrador_b2 | OP | adaptar | entrada operacional |
| 469 | `orquestrador_b2/tests/test_estilo_v2.py::Fluxo::test_lista_e_cta_da_entrega` | orquestrador_b2 | OP | adaptar | entrada operacional |
| 470 | `orquestrador_b2/tests/test_estilo_v2.py::Fluxo::test_menos_de_3_slides_bloqueia` | orquestrador_b2 | OP | baixo/central | fixture estatica;entrada operacional |
| 471 | `orquestrador_b2/tests/test_estilo_v2.py::Fluxo::test_relatorio_flags_e_estilo` | orquestrador_b2 | OP | adaptar | entrada operacional |
| 472 | `orquestrador_b2/tests/test_estilo_v2.py::Fluxo::test_sem_aprovacao_para_na_pendencia` | orquestrador_b2 | OP | baixo/central | fixture estatica;entrada operacional |
| 473 | `orquestrador_b2/tests/test_estilo_v2.py::Fluxo::test_sem_termos_proibidos_nos_slides_e_legenda` | orquestrador_b2 | OP | adaptar | entrada operacional |
| 474 | `orquestrador_b2/tests/test_estilo_v2.py::Fluxo::test_tres_carrosseis_concluidos_com_3_a_5_slides` | orquestrador_b2 | OP | adaptar | entrada operacional |
| 475 | `orquestrador_b2/tests/test_estilo_v2.py::Textos::test_avaliar_texto_reprova_termos` | orquestrador_b2 | INT | nenhum | — |
| 476 | `orquestrador_b2/tests/test_estilo_v2.py::Textos::test_cta_com_links_mostra_os_links_sem_frases_proibidas` | orquestrador_b2 | INT | nenhum | — |
| 477 | `orquestrador_b2/tests/test_estilo_v2.py::Textos::test_cta_sem_links_neutro` | orquestrador_b2 | INT | nenhum | — |
| 478 | `orquestrador_b2/tests/test_estilo_v2.py::Textos::test_destaque_numerico_extraido_do_fato` | orquestrador_b2 | INT | nenhum | — |
| 479 | `orquestrador_b2/tests/test_estilo_v2.py::Textos::test_titulos_curtos_e_sem_alegacao` | orquestrador_b2 | INT | nenhum | — |
| 480 | `orquestrador_b2/tests/test_estilo_v2.py::TitulosDaLista::test_derivacao_generica_com_fatos_novos` | orquestrador_b2 | INT | nenhum | — |
| 481 | `orquestrador_b2/tests/test_estilo_v2.py::TitulosDaLista::test_sem_informacao_suficiente_usa_titulo_neutro` | orquestrador_b2 | INT | nenhum | — |
| 482 | `orquestrador_b2/tests/test_estilo_v2.py::TitulosDaLista::test_titulo_nao_inventa_caracteristica` | orquestrador_b2 | INT | nenhum | — |
| 483 | `orquestrador_b2/tests/test_estilo_v2.py::TitulosDaLista::test_titulos_derivados_dos_fatos_das_fixtures` | orquestrador_b2 | INT | nenhum | — |
| 484 | `orquestrador_b2/tests/test_orquestrador_b2.py::AprovacaoTest::test_catalogo_nunca_e_criado_sem_raiz` | orquestrador_b2 | OP | baixo/central | fixture estatica;entrada operacional |
| 485 | `orquestrador_b2/tests/test_orquestrador_b2.py::AprovacaoTest::test_nunca_aprova_fotografia_real_nem_catalogo_persistente` | orquestrador_b2 | OP | baixo/central | fixture estatica;entrada operacional |
| 486 | `orquestrador_b2/tests/test_orquestrador_b2.py::AprovacaoTest::test_opcao_so_vale_para_a_fixture_reconhecida` | orquestrador_b2 | OP | baixo/central | fixture dinamica;fixture estatica;entrada operacional |
| 487 | `orquestrador_b2/tests/test_orquestrador_b2.py::AprovacaoTest::test_resolver_aprovacao_exige_opcao_fixture_e_catalogo_temporario` | orquestrador_b2 | EST | nenhum | fixture estatica |
| 488 | `orquestrador_b2/tests/test_orquestrador_b2.py::AprovacaoTest::test_sem_a_opcao_o_fluxo_para_com_aprovacao_pendente` | orquestrador_b2 | OP | baixo/central | fixture estatica;entrada operacional |
| 489 | `orquestrador_b2/tests/test_orquestrador_b2.py::CliTest::test_cli_nao_tem_opcao_para_habilitar_produtos_ou_dados_reais` | orquestrador_b2 | OP | baixo/central | fixture estatica;entrada operacional |
| 490 | `orquestrador_b2/tests/test_orquestrador_b2.py::CliTest::test_codigos_de_saida` | orquestrador_b2 | OP | baixo/central | fixture dinamica;fixture estatica;entrada operacional |
| 491 | `orquestrador_b2/tests/test_orquestrador_b2.py::CliTest::test_links_via_cli` | orquestrador_b2 | OP | baixo/central | fixture estatica;entrada operacional;http negativo |
| 492 | `orquestrador_b2/tests/test_orquestrador_b2.py::CliTest::test_usos_invalidos` | orquestrador_b2 | OP | baixo/central | fixture estatica;entrada operacional |
| 493 | `orquestrador_b2/tests/test_orquestrador_b2.py::DeterminismoTest::test_mesmas_entradas_mesmas_saidas` | orquestrador_b2 | OP | baixo/central | fixture estatica;entrada operacional |
| 494 | `orquestrador_b2/tests/test_orquestrador_b2.py::FluxoCompletoTest::test_aprovacao_de_teste_registrada_sem_valor_de_homologacao` | orquestrador_b2 | OP | baixo/central | fixture estatica;entrada operacional |
| 495 | `orquestrador_b2/tests/test_orquestrador_b2.py::FluxoCompletoTest::test_arquivos_de_saida` | orquestrador_b2 | OP | baixo/central | fixture estatica;entrada operacional |
| 496 | `orquestrador_b2/tests/test_orquestrador_b2.py::FluxoCompletoTest::test_catalogo_persistente_intacto_e_catalogo_temporario_na_saida` | orquestrador_b2 | OP | baixo/central | fixture estatica;entrada operacional |
| 497 | `orquestrador_b2/tests/test_orquestrador_b2.py::FluxoCompletoTest::test_entre_3_e_5_slides_na_resolucao_correta` | orquestrador_b2 | OP | baixo/central | fixture estatica;entrada operacional |
| 498 | `orquestrador_b2/tests/test_orquestrador_b2.py::FluxoCompletoTest::test_estrutura_do_carrossel` | orquestrador_b2 | OP | baixo/central | fixture estatica;entrada operacional |
| 499 | `orquestrador_b2/tests/test_orquestrador_b2.py::FluxoCompletoTest::test_ficha_permanece_editorial_elegivel` | orquestrador_b2 | OP | baixo/central | fixture estatica;entrada operacional |
| 500 | `orquestrador_b2/tests/test_orquestrador_b2.py::FluxoCompletoTest::test_folha_de_contato` | orquestrador_b2 | OP | baixo/central | fixture estatica;entrada operacional |
| 501 | `orquestrador_b2/tests/test_orquestrador_b2.py::FluxoCompletoTest::test_relatorios_completos_e_consistentes_com_os_arquivos` | orquestrador_b2 | OP | baixo/central | fixture estatica;entrada operacional |
| 502 | `orquestrador_b2/tests/test_orquestrador_b2.py::FluxoCompletoTest::test_restricoes_registradas` | orquestrador_b2 | OP | baixo/central | fixture estatica;entrada operacional;guarda estatica ou golden ou flags |
| 503 | `orquestrador_b2/tests/test_orquestrador_b2.py::FluxoCompletoTest::test_sem_conteudo_comercial_nos_slides_e_na_legenda` | orquestrador_b2 | OP | baixo/central | fixture estatica;entrada operacional |
| 504 | `orquestrador_b2/tests/test_orquestrador_b2.py::FluxoCompletoTest::test_status_e_etapas` | orquestrador_b2 | OP | baixo/central | fixture estatica;entrada operacional |
| 505 | `orquestrador_b2/tests/test_orquestrador_b2.py::FolhaTest::test_dimensoes_por_quantidade_e_determinismo` | orquestrador_b2 | INT | nenhum | — |
| 506 | `orquestrador_b2/tests/test_orquestrador_b2.py::FolhaTest::test_faixa_de_aviso_vermelha_no_topo` | orquestrador_b2 | INT | nenhum | — |
| 507 | `orquestrador_b2/tests/test_orquestrador_b2.py::FolhaTest::test_sem_slides_e_erro` | orquestrador_b2 | INT | nenhum | — |
| 508 | `orquestrador_b2/tests/test_orquestrador_b2.py::FolhaTest::test_texto_de_rascunho_e_numeracao_aparecem` | orquestrador_b2 | INT | nenhum | — |
| 509 | `orquestrador_b2/tests/test_orquestrador_b2.py::LinksOficiaisTest::test_links_validos_fornecidos_entram_no_cta_e_na_legenda` | orquestrador_b2 | OP | baixo/central | fixture estatica;entrada operacional |
| 510 | `orquestrador_b2/tests/test_orquestrador_b2.py::NumeroDeSlidesTest::test_de_3_a_5_slides_renderizados_conforme_os_fatos` | orquestrador_b2 | OP | baixo/central | fixture dinamica;fixture estatica;entrada operacional |
| 511 | `orquestrador_b2/tests/test_orquestrador_b2.py::NumeroDeSlidesTest::test_fixture_continua_sendo_a_unica_reconhecida_sem_patch` | orquestrador_b2 | EST | nenhum | fixture estatica |
| 512 | `orquestrador_b2/tests/test_orquestrador_b2.py::RejeicoesTest::test_alegacoes_comerciais_e_campos_de_preco_sao_rejeitados` | orquestrador_b2 | OP | baixo/central | fixture dinamica;fixture estatica;entrada operacional |
| 513 | `orquestrador_b2/tests/test_orquestrador_b2.py::RejeicoesTest::test_ficha_ilegivel_ou_json_invalido` | orquestrador_b2 | OP | baixo/central | fixture dinamica;entrada operacional |
| 514 | `orquestrador_b2/tests/test_orquestrador_b2.py::RejeicoesTest::test_links_invalidos_bloqueiam_o_carrossel` | orquestrador_b2 | OP | baixo/central | fixture estatica;entrada operacional;http negativo |
| 515 | `orquestrador_b2/tests/test_orquestrador_b2.py::RejeicoesTest::test_lote_com_origem_de_agente_e_bloqueado_depois_do_receptor` | orquestrador_b2 | OP | baixo/central | fixture dinamica;fixture estatica;entrada operacional |
| 516 | `orquestrador_b2/tests/test_orquestrador_b2.py::RejeicoesTest::test_origem_falsa_e_rejeitada` | orquestrador_b2 | OP | baixo/central | fixture dinamica;fixture estatica;entrada operacional |
| 517 | `orquestrador_b2/tests/test_orquestrador_b2.py::RejeicoesTest::test_produto_real_e_rejeitado` | orquestrador_b2 | OP | baixo/central | fixture dinamica;fixture estatica;entrada operacional |
| 518 | `orquestrador_b2/tests/test_orquestrador_b2.py::RejeicoesTest::test_saida_dentro_do_repositorio_e_recusada` | orquestrador_b2 | OP | baixo/central | fixture estatica;entrada operacional |
| 519 | `orquestrador_b2/tests/test_orquestrador_b2.py::RejeicoesTest::test_urls_invalidas_sao_rejeitadas` | orquestrador_b2 | OP | baixo/central | fixture dinamica;fixture estatica;entrada operacional;http negativo |
| 520 | `orquestrador_b2/tests/test_orquestrador_b2.py::SemRedeESemVersionamentoTest::test_fluxo_roda_com_a_rede_bloqueada` | orquestrador_b2 | OP | baixo/central | fixture estatica;entrada operacional |
| 521 | `orquestrador_b2/tests/test_orquestrador_b2.py::SemRedeESemVersionamentoTest::test_modulos_sem_rede_processos_ou_ambiente` | orquestrador_b2 | INT | nenhum | — |
| 522 | `orquestrador_b2/tests/test_orquestrador_b2.py::SemRedeESemVersionamentoTest::test_nada_e_versionado_nem_alterado_no_repositorio` | orquestrador_b2 | OP | baixo/central | fixture estatica;entrada operacional |
| 523 | `orquestrador_b2/tests/test_orquestrador_b2.py::SemRedeESemVersionamentoTest::test_o_fluxo_nao_altera_as_implementacoes_reutilizadas` | orquestrador_b2 | INT | nenhum | — |
| 524 | `orquestrador_b2/tests/test_orquestrador_b2.py::ValidacaoDeConteudoTest::test_rede_de_seguranca_bloqueia_conteudo_comercial_url_e_rotulo_ausente` | orquestrador_b2 | INT | nenhum | — |
| 525 | `tests/test_fundo_marca.py::CatalogoTest::test_catalogo_do_repositorio_nunca_e_tocado` | tests/gerador+fundo | INT | nenhum | — |
| 526 | `tests/test_fundo_marca.py::CatalogoTest::test_catalogo_e_obrigatorio_nao_ha_padrao` | tests/gerador+fundo | INT | nenhum | — |
| 527 | `tests/test_fundo_marca.py::CatalogoTest::test_catalogo_e_persistido_so_no_temporario` | tests/gerador+fundo | INT | nenhum | — |
| 528 | `tests/test_fundo_marca.py::CatalogoTest::test_mesmo_conteudo_nao_duplica_e_variantes_geram_novos_ids` | tests/gerador+fundo | INT | nenhum | — |
| 529 | `tests/test_fundo_marca.py::CatalogoTest::test_provedores_existentes_preservados_e_novo_registrado` | tests/gerador+fundo | INT | nenhum | — |
| 530 | `tests/test_fundo_marca.py::CatalogoTest::test_registro_nasce_pendente_e_nunca_aprovado` | tests/gerador+fundo | INT | nenhum | — |
| 531 | `tests/test_fundo_marca.py::CatalogoTest::test_selecao_do_gerador_exige_aprovacao_humana` | tests/gerador+fundo | INT | nenhum | — |
| 532 | `tests/test_fundo_marca.py::IdentidadeVisualTest::test_contraste_suficiente_para_o_validador_do_gerador` | tests/gerador+fundo | INT | nenhum | — |
| 533 | `tests/test_fundo_marca.py::IdentidadeVisualTest::test_funciona_nos_layouts_existentes_do_gerador` | tests/gerador+fundo | INT | nenhum | — |
| 534 | `tests/test_fundo_marca.py::IdentidadeVisualTest::test_logotipo_oficial_e_usado_sem_ser_modificado` | tests/gerador+fundo | INT | nenhum | — |
| 535 | `tests/test_fundo_marca.py::IdentidadeVisualTest::test_paleta_dominante_e_a_da_marca` | tests/gerador+fundo | INT | nenhum | — |
| 536 | `tests/test_fundo_marca.py::IdentidadeVisualTest::test_sem_fotos_nem_textos_de_produto` | tests/gerador+fundo | INT | nenhum | — |
| 537 | `tests/test_fundo_marca.py::IdentidadeVisualTest::test_usa_as_cores_oficiais_do_modulo_de_identidade` | tests/gerador+fundo | INT | nenhum | — |
| 538 | `tests/test_fundo_marca.py::ImagemTest::test_determinismo_bytes_e_sha256` | tests/gerador+fundo | INT | nenhum | — |
| 539 | `tests/test_fundo_marca.py::ImagemTest::test_determinismo_sobrevive_a_cache_limpo_e_a_outras_chamadas` | tests/gerador+fundo | INT | nenhum | — |
| 540 | `tests/test_fundo_marca.py::ImagemTest::test_dimensoes_formato_e_modo` | tests/gerador+fundo | INT | nenhum | — |
| 541 | `tests/test_fundo_marca.py::ImagemTest::test_golden_estavel_de_uma_variante` | tests/gerador+fundo | INT | nenhum | — |
| 542 | `tests/test_fundo_marca.py::ImagemTest::test_variante_invalida` | tests/gerador+fundo | INT | nenhum | — |
| 543 | `tests/test_fundo_marca.py::ImagemTest::test_variantes_distintas_geram_imagens_distintas` | tests/gerador+fundo | INT | nenhum | — |
| 544 | `tests/test_fundo_marca.py::IntegracaoComCarrosselTest::test_fundo_aprovado_manualmente_e_usado_com_o_rotulo_arte_ilustrativa` | tests/gerador+fundo | DIN | nenhum | fixture dinamica |
| 545 | `tests/test_fundo_marca.py::IntegracaoComCarrosselTest::test_fundo_nao_e_aceito_como_foto_real_autorizada` | tests/gerador+fundo | DIN | nenhum | fixture dinamica |
| 546 | `tests/test_fundo_marca.py::IntegracaoComCarrosselTest::test_fundo_sem_aprovacao_permanece_bloqueado` | tests/gerador+fundo | DIN | nenhum | fixture dinamica |
| 547 | `tests/test_fundo_marca.py::IntegracaoComCarrosselTest::test_saida_e_compativel_com_o_gerador_existente` | tests/gerador+fundo | DIN | nenhum | fixture dinamica |
| 548 | `tests/test_fundo_marca.py::SemRedeTest::test_geracao_e_registro_rodam_com_a_rede_bloqueada` | tests/gerador+fundo | INT | nenhum | — |
| 549 | `tests/test_fundo_marca.py::SemRedeTest::test_modulo_sem_rede_processos_ou_ambiente` | tests/gerador+fundo | INT | nenhum | — |
| 550 | `tests/test_gerador.py::TestFluxSemRede::test_exige_confirmacao` | tests/gerador+fundo | OP | baixo/central | entrada operacional |
| 551 | `tests/test_gerador.py::TestFluxSemRede::test_registra_e_protege_cota` | tests/gerador+fundo | OP | baixo/central | entrada operacional |
| 552 | `tests/test_gerador.py::TestImportacao::test_aprovacao_exige_nome` | tests/gerador+fundo | OP | baixo/central | entrada operacional |
| 553 | `tests/test_gerador.py::TestImportacao::test_aprovado_na_importacao` | tests/gerador+fundo | OP | baixo/central | entrada operacional |
| 554 | `tests/test_gerador.py::TestImportacao::test_duplicata_por_hash` | tests/gerador+fundo | OP | baixo/central | entrada operacional |
| 555 | `tests/test_gerador.py::TestImportacao::test_jpg_png_webp` | tests/gerador+fundo | OP | baixo/central | entrada operacional |
| 556 | `tests/test_gerador.py::TestImportacao::test_orientacao_exif` | tests/gerador+fundo | OP | baixo/central | entrada operacional |
| 557 | `tests/test_gerador.py::TestImportacao::test_rejeita_invalidas` | tests/gerador+fundo | OP | baixo/central | fixture dinamica;entrada operacional |
| 558 | `tests/test_gerador.py::TestSelecaoComposicao::test_carrossel_tres_layouts` | tests/gerador+fundo | OP | baixo/central | entrada operacional |
| 559 | `tests/test_gerador.py::TestSelecaoComposicao::test_cobrir_nao_deforma` | tests/gerador+fundo | INT | nenhum | — |
| 560 | `tests/test_gerador.py::TestSelecaoComposicao::test_config_invalida` | tests/gerador+fundo | DIN | nenhum | fixture dinamica |
| 561 | `tests/test_gerador.py::TestSelecaoComposicao::test_exemplo_versionado_e_valido` | tests/gerador+fundo | EST | nenhum | fixture estatica |
| 562 | `tests/test_gerador.py::TestSelecaoComposicao::test_pendente_bloqueada` | tests/gerador+fundo | OP | baixo/central | entrada operacional |
| 563 | `tests/test_gerador.py::TestSelecaoComposicao::test_rejeitada_e_ausente` | tests/gerador+fundo | OP | baixo/central | entrada operacional |
| 564 | `tests/test_gerador.py::TestSelecaoComposicao::test_sem_repeticao_automatica` | tests/gerador+fundo | OP | baixo/central | entrada operacional |
| 565 | `tests/test_gerador.py::TestSelecaoComposicao::test_texto_longo_demais` | tests/gerador+fundo | OP | baixo/central | entrada operacional |
| 566 | `tests/test_gerador.py::TestSelecaoComposicao::test_validacao_detecta_foto_lisa` | tests/gerador+fundo | OP | baixo/central | entrada operacional |
| 567 | `tests/test_b2r_compat.py::ConstantesEHelpersTest::test_constantes_novas` | tests/b2r_compat_layouts | INT | nenhum | — |
| 568 | `tests/test_b2r_compat.py::ConstantesEHelpersTest::test_contraste_efetivo_aprova_painel_controlado_e_reprova_fundo_claro_ou_variavel` | tests/b2r_compat_layouts | INT | nenhum | — |
| 569 | `tests/test_b2r_compat.py::ConstantesEHelpersTest::test_maior_area_vazia` | tests/b2r_compat_layouts | INT | nenhum | — |
| 570 | `tests/test_b2r_compat.py::ConstantesEHelpersTest::test_razao_de_contraste_wcag` | tests/b2r_compat_layouts | INT | nenhum | — |
| 571 | `tests/test_b2r_compat.py::ConstantesEHelpersTest::test_validar_slide_antigo_continua_com_a_mesma_assinatura` | tests/b2r_compat_layouts | INT | nenhum | — |
| 572 | `tests/test_b2r_compat.py::FundoSemMarcaTest::test_contraste_visual_continua_suficiente_sem_marca` | tests/b2r_compat_layouts | INT | nenhum | — |
| 573 | `tests/test_b2r_compat.py::FundoSemMarcaTest::test_determinismo_e_validacao` | tests/b2r_compat_layouts | INT | nenhum | — |
| 574 | `tests/test_b2r_compat.py::FundoSemMarcaTest::test_registro_sem_marca_e_pendente_e_distinto` | tests/b2r_compat_layouts | INT | nenhum | — |
| 575 | `tests/test_b2r_compat.py::FundoSemMarcaTest::test_sem_marca_nao_tem_logo_e_o_resto_e_identico` | tests/b2r_compat_layouts | INT | nenhum | — |
| 576 | `tests/test_b2r_compat.py::RegressaoDosCaminhosAntigosTest::test_assinaturas_anteriores_preservadas` | tests/b2r_compat_layouts | INT | nenhum | — |
| 577 | `tests/test_b2r_compat.py::RegressaoDosCaminhosAntigosTest::test_constantes_antigas_de_identidade_nao_mudaram` | tests/b2r_compat_layouts | INT | nenhum | — |
| 578 | `tests/test_b2r_compat.py::RegressaoDosCaminhosAntigosTest::test_fundos_das_12_variantes_identicos_ao_anterior` | tests/b2r_compat_layouts | INT | nenhum | — |
| 579 | `tests/test_b2r_compat.py::RegressaoDosCaminhosAntigosTest::test_golden_do_modo_1_0` | tests/b2r_compat_layouts | EST | nenhum | fixture estatica |
| 580 | `tests/test_b2r_compat.py::RegressaoDosCaminhosAntigosTest::test_layouts_antigos_identicos_ao_anterior` | tests/b2r_compat_layouts | INT | nenhum | — |
| 581 | `tests/test_b2r_compat.py::RegressaoDosCaminhosAntigosTest::test_referencia_vem_do_commit_base` | tests/b2r_compat_layouts | INT | nenhum | — |
| 582 | `tests/test_b2r_compat.py::RegressaoDosCaminhosAntigosTest::test_slides_do_b2_antigo_identicos_ao_anterior` | tests/b2r_compat_layouts | OP | baixo/central | fixture estatica;entrada operacional |
| 583 | `tests/test_b2r_compat.py::RodapeGrandeTest::test_contador_tem_pelo_menos_38px` | tests/b2r_compat_layouts | INT | nenhum | — |
| 584 | `tests/test_b2r_compat.py::RodapeGrandeTest::test_grande_tem_logo_de_160px_inteiro_dentro_da_margem` | tests/b2r_compat_layouts | INT | nenhum | — |
| 585 | `tests/test_b2r_compat.py::RodapeGrandeTest::test_padrao_nao_mudou` | tests/b2r_compat_layouts | INT | nenhum | — |
| 586 | `tests/test_b2r_compat.py::RodapeGrandeTest::test_sem_contador_quando_ha_um_unico_slide` | tests/b2r_compat_layouts | INT | nenhum | — |
| 587 | `tests/test_b2r_layouts.py::IlustracoesTest::test_categoria_de_ficha` | tests/b2r_compat_layouts | INT | nenhum | — |
| 588 | `tests/test_b2r_layouts.py::IlustracoesTest::test_categoria_desconhecida_usa_generica` | tests/b2r_compat_layouts | INT | nenhum | — |
| 589 | `tests/test_b2r_layouts.py::IlustracoesTest::test_categorias_visualmente_distintas` | tests/b2r_compat_layouts | INT | nenhum | — |
| 590 | `tests/test_b2r_layouts.py::IlustracoesTest::test_cores_da_marca_e_riqueza_visual` | tests/b2r_compat_layouts | INT | nenhum | — |
| 591 | `tests/test_b2r_layouts.py::IlustracoesTest::test_determinismo_das_seis_categorias` | tests/b2r_compat_layouts | INT | nenhum | — |
| 592 | `tests/test_b2r_layouts.py::IlustracoesTest::test_registro_pendente_no_catalogo_temporario` | tests/b2r_compat_layouts | INT | nenhum | — |
| 593 | `tests/test_b2r_layouts.py::IlustracoesTest::test_seis_categorias_e_tamanho` | tests/b2r_compat_layouts | INT | nenhum | — |
| 594 | `tests/test_b2r_layouts.py::IlustracoesTest::test_sem_texto_fotos_ou_marcas` | tests/b2r_compat_layouts | INT | nenhum | — |
| 595 | `tests/test_b2r_layouts.py::IntegracaoComOGeradorTest::test_campos_do_slide_aceitos_pelo_carregador` | tests/b2r_compat_layouts | DIN | nenhum | fixture dinamica |
| 596 | `tests/test_b2r_layouts.py::IntegracaoComOGeradorTest::test_gerar_renderiza_os_quatro_layouts_novos_e_o_status_e_pronto` | tests/b2r_compat_layouts | INT | nenhum | — |
| 597 | `tests/test_b2r_layouts.py::IntegracaoComOGeradorTest::test_imagem_pendente_continua_bloqueada_pelo_gerador` | tests/b2r_compat_layouts | INT | nenhum | — |
| 598 | `tests/test_b2r_layouts.py::LayoutsNovosTest::test_area_decorativa_dentro_do_limite` | tests/b2r_compat_layouts | INT | nenhum | — |
| 599 | `tests/test_b2r_layouts.py::LayoutsNovosTest::test_conteudo_que_nao_cabe_nao_e_reduzido_nem_truncado` | tests/b2r_compat_layouts | INT | nenhum | — |
| 600 | `tests/test_b2r_layouts.py::LayoutsNovosTest::test_cta_tem_dois_botoes_nomeados_e_nenhum_link_inventado` | tests/b2r_compat_layouts | INT | nenhum | — |
| 601 | `tests/test_b2r_layouts.py::LayoutsNovosTest::test_destaque_sem_numero_e_lista_funcionam_com_fonte_grande` | tests/b2r_compat_layouts | INT | nenhum | — |
| 602 | `tests/test_b2r_layouts.py::LayoutsNovosTest::test_logo_inteiro_sem_cortes_nos_pixels` | tests/b2r_compat_layouts | INT | nenhum | — |
| 603 | `tests/test_b2r_layouts.py::LayoutsNovosTest::test_nada_fora_da_area_segura_e_logo_inteiro_de_160px` | tests/b2r_compat_layouts | INT | nenhum | — |
| 604 | `tests/test_b2r_layouts.py::LayoutsNovosTest::test_numero_e_unidade_grandes_no_destaque` | tests/b2r_compat_layouts | INT | nenhum | — |
| 605 | `tests/test_b2r_layouts.py::LayoutsNovosTest::test_registrados_e_os_antigos_continuam` | tests/b2r_compat_layouts | INT | nenhum | — |
| 606 | `tests/test_b2r_layouts.py::LayoutsNovosTest::test_resolucao_e_assinatura` | tests/b2r_compat_layouts | INT | nenhum | — |
| 607 | `tests/test_b2r_layouts.py::LayoutsNovosTest::test_rotulo_arte_ilustrativa_em_todos` | tests/b2r_compat_layouts | INT | nenhum | — |
| 608 | `tests/test_b2r_layouts.py::LayoutsNovosTest::test_sem_texto_nao_muda_a_geometria` | tests/b2r_compat_layouts | INT | nenhum | — |
| 609 | `tests/test_b2r_layouts.py::LayoutsNovosTest::test_tamanhos_minimos_de_fonte` | tests/b2r_compat_layouts | INT | nenhum | — |
| 610 | `tests/test_b2r_layouts.py::LayoutsNovosTest::test_texto_sem_truncamento_e_sem_reticencias` | tests/b2r_compat_layouts | INT | nenhum | — |
| 611 | `tests/test_b2r_layouts.py::LayoutsNovosTest::test_validacao_antiga_do_gerador_aprova_os_novos_layouts` | tests/b2r_compat_layouts | INT | nenhum | — |
| 612 | `tests/test_b2r_layouts.py::LayoutsNovosTest::test_validacao_b2r_aprova_texto_curto_medio_e_longo` | tests/b2r_compat_layouts | INT | nenhum | — |
| 613 | `tests/test_b2r_layouts.py::LayoutsNovosTest::test_validador_b2r_reprova_o_que_deve_reprovar` | tests/b2r_compat_layouts | INT | nenhum | — |
| 614 | `tests/test_b2r_referencia_regressao.py::Cenarios::test_cenario_a_codificador_equivalente_com_evidencia_valida` | tests/b2r_referencia_regressao | OP | baixo/central | fixture estatica;entrada operacional |
| 615 | `tests/test_b2r_referencia_regressao.py::Cenarios::test_cenario_b_codificador_diferente` | tests/b2r_referencia_regressao | OP | baixo/central | fixture estatica;entrada operacional |
| 616 | `tests/test_b2r_referencia_regressao.py::Cenarios::test_cenario_c_aparentemente_equivalente_sem_evidencia` | tests/b2r_referencia_regressao | OP | baixo/central | fixture estatica;entrada operacional |
| 617 | `tests/test_b2r_referencia_regressao.py::Cenarios::test_cenario_d_conteudo_alterado_com_codificador_diferente` | tests/b2r_referencia_regressao | OP | baixo/central | fixture estatica;entrada operacional |
| 618 | `tests/test_b2r_referencia_regressao.py::Mutacao::test_1_alteracao_de_um_pixel` | tests/b2r_referencia_regressao | OP | baixo/central | fixture estatica;entrada operacional |
| 619 | `tests/test_b2r_referencia_regressao.py::Mutacao::test_1b_pixel_alterado_com_bytes_png_recodificados_ainda_reprova_em_ambiente_diferente` | tests/b2r_referencia_regressao | OP | baixo/central | fixture estatica;entrada operacional |
| 620 | `tests/test_b2r_referencia_regressao.py::Mutacao::test_2_alteracao_do_conteudo_do_carrossel` | tests/b2r_referencia_regressao | OP | baixo/central | fixture estatica;entrada operacional |
| 621 | `tests/test_b2r_referencia_regressao.py::Mutacao::test_3_alteracao_de_dimensao` | tests/b2r_referencia_regressao | OP | baixo/central | fixture estatica;entrada operacional |
| 622 | `tests/test_b2r_referencia_regressao.py::Mutacao::test_4_alteracao_de_modo_de_cor` | tests/b2r_referencia_regressao | OP | baixo/central | fixture estatica;entrada operacional |
| 623 | `tests/test_b2r_referencia_regressao.py::Mutacao::test_5_alteracao_de_um_jpeg` | tests/b2r_referencia_regressao | OP | baixo/central | fixture estatica;entrada operacional |
| 624 | `tests/test_b2r_referencia_regressao.py::Mutacao::test_5b_nome_ordem_e_quantidade_dos_slides` | tests/b2r_referencia_regressao | OP | baixo/central | fixture estatica;entrada operacional |
| 625 | `tests/test_b2r_referencia_regressao.py::Mutacao::test_6_bytes_png_alterados_com_ambiente_equivalente` | tests/b2r_referencia_regressao | OP | baixo/central | fixture estatica;entrada operacional |
| 626 | `tests/test_b2r_referencia_regressao.py::Mutacao::test_7_ambiente_diferente_simulado_mantem_a_comparacao_de_pixels` | tests/b2r_referencia_regressao | OP | baixo/central | fixture estatica;entrada operacional |
| 627 | `tests/test_b2r_referencia_regressao.py::Mutacao::test_8_ambiente_declarado_equivalente_sem_evidencia` | tests/b2r_referencia_regressao | OP | baixo/central | fixture estatica;entrada operacional |
| 628 | `tests/test_b2r_referencia_regressao.py::Mutacao::test_9_falha_de_determinismo_entre_duas_execucoes` | tests/b2r_referencia_regressao | OP | baixo/central | fixture estatica;entrada operacional |
| 629 | `tests/test_b2r_referencia_regressao.py::Mutacao::test_conteudo_nunca_dispensado` | tests/b2r_referencia_regressao | OP | baixo/central | fixture estatica;entrada operacional |
| 630 | `tests/test_b2r_referencia_regressao.py::Reais::test_conteudo_de_referencia_completo` | tests/b2r_referencia_regressao | OP | baixo/central | fixture estatica;entrada operacional |
| 631 | `tests/test_b2r_referencia_regressao.py::Reais::test_determinismo_local_bytes_identicos` | tests/b2r_referencia_regressao | OP | baixo/central | fixture estatica;entrada operacional |
| 632 | `tests/test_b2r_referencia_regressao.py::Reais::test_head_reproduz_a_referencia_neste_ambiente` | tests/b2r_referencia_regressao | OP | baixo/central | fixture estatica;entrada operacional |
| 633 | `tests/test_b2r_referencia_regressao.py::Reais::test_hipotese_o_codificador_muda_bytes_nao_pixels` | tests/b2r_referencia_regressao | OP | baixo/central | fixture estatica;entrada operacional |
| 634 | `tests/test_b2r_referencia_regressao.py::Reais::test_o_ambiente_atual_e_declarado_equivalente_por_evidencia_medida` | tests/b2r_referencia_regressao | OP | baixo/central | fixture estatica;entrada operacional |
| 635 | `tests/test_b2r_referencia_regressao.py::Reais::test_referencia_historica_preservada_no_json` | tests/b2r_referencia_regressao | OP | baixo/central | fixture estatica;entrada operacional |
| 636 | `reels/tests/test_config.py::TestConfig::test_comments_ignored` | reels | INT | nenhum | — |
| 637 | `reels/tests/test_config.py::TestConfig::test_deep_merge` | reels | INT | nenhum | — |
| 638 | `reels/tests/test_config.py::TestConfig::test_enum_and_ranges` | reels | INT | nenhum | — |
| 639 | `reels/tests/test_config.py::TestConfig::test_hook_lines_limit` | reels | INT | nenhum | — |
| 640 | `reels/tests/test_config.py::TestConfig::test_missing_required` | reels | INT | nenhum | — |
| 641 | `reels/tests/test_config.py::TestConfig::test_pilot_loads_with_defaults` | reels | INT | nenhum | — |
| 642 | `reels/tests/test_config.py::TestConfig::test_unknown_key_is_error` | reels | INT | nenhum | — |
| 643 | `reels/tests/test_config.py::TestConfig::test_unknown_top_level_key` | reels | INT | nenhum | — |
| 644 | `reels/tests/test_config.py::TestConfig::test_wrong_types` | reels | INT | nenhum | — |
| 645 | `reels/tests/test_e2e_pilot.py::TestE2E::test_byte_identical_with_one_thread` | reels | OP | exige decisão | fixture dinamica;entrada operacional |
| 646 | `reels/tests/test_e2e_pilot.py::TestE2E::test_cta_only_independent_and_deterministic` | reels | OP | exige decisão | entrada operacional |
| 647 | `reels/tests/test_e2e_pilot.py::TestE2E::test_frames_and_motion` | reels | OP | exige decisão | entrada operacional |
| 648 | `reels/tests/test_e2e_pilot.py::TestE2E::test_pilot_approved` | reels | OP | exige decisão | entrada operacional |
| 649 | `reels/tests/test_e2e_pilot.py::TestE2E::test_pilot_specs` | reels | OP | exige decisão | entrada operacional |
| 650 | `reels/tests/test_e2e_pilot.py::TestE2E::test_second_config_without_code_change` | reels | OP | exige decisão | entrada operacional |
| 651 | `reels/tests/test_e2e_pilot.py::TestE2E::test_three_distinct_categories_synthetic_labeled` | reels | OP | exige decisão | entrada operacional |
| 652 | `reels/tests/test_ffmpeg_build.py::TestFFmpegBuild::test_final_command_args` | reels | OP | exige decisão | entrada operacional |
| 653 | `reels/tests/test_ffmpeg_build.py::TestFFmpegBuild::test_licensed_audio_graph` | reels | OP | exige decisão | entrada operacional |
| 654 | `reels/tests/test_ffmpeg_build.py::TestFFmpegBuild::test_no_shell_true_anywhere` | reels | OP | exige decisão | entrada operacional |
| 655 | `reels/tests/test_ffmpeg_build.py::TestFFmpegBuild::test_run_rejects_string` | reels | OP | exige decisão | entrada operacional |
| 656 | `reels/tests/test_ffmpeg_build.py::TestFFmpegBuild::test_segment_command` | reels | OP | exige decisão | entrada operacional |
| 657 | `reels/tests/test_ffmpeg_build.py::TestFFmpegBuild::test_silent_track_option` | reels | OP | exige decisão | entrada operacional |
| 658 | `reels/tests/test_ffmpeg_build.py::TestFFmpegBuild::test_xfade_offsets_match_timeline` | reels | OP | exige decisão | entrada operacional |
| 659 | `reels/tests/test_layers.py::TestLayers::test_balanced_no_orphan_and_dash` | reels | OP | exige decisão | entrada operacional |
| 660 | `reels/tests/test_layers.py::TestLayers::test_check_layers_detects_violations` | reels | OP | exige decisão | entrada operacional |
| 661 | `reels/tests/test_layers.py::TestLayers::test_contrast` | reels | OP | exige decisão | entrada operacional |
| 662 | `reels/tests/test_layers.py::TestLayers::test_demo_label_on_every_segment` | reels | OP | exige decisão | entrada operacional |
| 663 | `reels/tests/test_layers.py::TestLayers::test_font_minimums` | reels | OP | exige decisão | entrada operacional |
| 664 | `reels/tests/test_layers.py::TestLayers::test_logo_aspect_and_presence` | reels | OP | exige decisão | entrada operacional |
| 665 | `reels/tests/test_layers.py::TestLayers::test_logo_colors_untouched` | reels | OP | exige decisão | entrada operacional |
| 666 | `reels/tests/test_layers.py::TestLayers::test_no_price_layers` | reels | OP | exige decisão | entrada operacional |
| 667 | `reels/tests/test_layers.py::TestLayers::test_overflow_reported` | reels | OP | exige decisão | entrada operacional |
| 668 | `reels/tests/test_layers.py::TestLayers::test_pilot_layers_ok` | reels | OP | exige decisão | entrada operacional |
| 669 | `reels/tests/test_layers.py::TestLayers::test_wrap_long_word_forced` | reels | OP | exige decisão | entrada operacional |
| 670 | `reels/tests/test_layers.py::TestLayers::test_wrap_respects_real_width` | reels | OP | exige decisão | entrada operacional |
| 671 | `reels/tests/test_rules.py::TestRules::test_audio_rules` | reels | INT | nenhum | — |
| 672 | `reels/tests/test_rules.py::TestRules::test_button_without_channel` | reels | INT | nenhum | — |
| 673 | `reels/tests/test_rules.py::TestRules::test_channels_official_only` | reels | INT | nenhum | — |
| 674 | `reels/tests/test_rules.py::TestRules::test_disclosure_required` | reels | INT | nenhum | — |
| 675 | `reels/tests/test_rules.py::TestRules::test_discount_stock_rating_blocked` | reels | INT | nenhum | — |
| 676 | `reels/tests/test_rules.py::TestRules::test_extra_forbidden_terms` | reels | INT | nenhum | — |
| 677 | `reels/tests/test_rules.py::TestRules::test_forbidden_terms_any_field_and_accents` | reels | INT | nenhum | — |
| 678 | `reels/tests/test_rules.py::TestRules::test_forbidden_word_boundaries` | reels | INT | nenhum | — |
| 679 | `reels/tests/test_rules.py::TestRules::test_illustrative_gets_label` | reels | INT | nenhum | — |
| 680 | `reels/tests/test_rules.py::TestRules::test_pilot_passes` | reels | INT | nenhum | — |
| 681 | `reels/tests/test_rules.py::TestRules::test_price_with_verification_but_synthetic` | reels | INT | nenhum | — |
| 682 | `reels/tests/test_rules.py::TestRules::test_price_without_verification` | reels | INT | nenhum | — |
| 683 | `reels/tests/test_rules.py::TestRules::test_product_model_on_non_real` | reels | INT | nenhum | — |
| 684 | `reels/tests/test_rules.py::TestRules::test_remote_and_missing_sources` | reels | INT | nenhum | — |
| 685 | `reels/tests/test_rules.py::TestRules::test_synthetic_requires_demo_label` | reels | INT | nenhum | — |
| 686 | `reels/tests/test_timeline.py::TestMotion::test_camera_window_bounds_and_continuity` | reels | INT | nenhum | — |
| 687 | `reels/tests/test_timeline.py::TestMotion::test_easing_endpoints_monotonic` | reels | INT | nenhum | — |
| 688 | `reels/tests/test_timeline.py::TestMotion::test_frames_and_smoothness` | reels | INT | nenhum | — |
| 689 | `reels/tests/test_timeline.py::TestMotion::test_overlay_slide` | reels | INT | nenhum | — |
| 690 | `reels/tests/test_timeline.py::TestMotion::test_zoompan_expression` | reels | INT | nenhum | — |
| 691 | `reels/tests/test_timeline.py::TestTimeline::test_content_window` | reels | INT | nenhum | — |
| 692 | `reels/tests/test_timeline.py::TestTimeline::test_cta_min` | reels | INT | nenhum | — |
| 693 | `reels/tests/test_timeline.py::TestTimeline::test_cta_only` | reels | INT | nenhum | — |
| 694 | `reels/tests/test_timeline.py::TestTimeline::test_frame_quantization` | reels | INT | nenhum | — |
| 695 | `reels/tests/test_timeline.py::TestTimeline::test_hook_limit` | reels | INT | nenhum | — |
| 696 | `reels/tests/test_timeline.py::TestTimeline::test_pilot_offsets_and_total` | reels | INT | nenhum | — |
| 697 | `reels/tests/test_timeline.py::TestTimeline::test_total_out_of_range` | reels | INT | nenhum | — |
| 698 | `reels/tests/test_timeline.py::TestTimeline::test_transitions_consume_scene` | reels | INT | nenhum | — |
| 699 | `reels/tests/test_validate.py::TestValidate::test_duration_range_enforced` | reels | INT | nenhum | — |
| 700 | `reels/tests/test_validate.py::TestValidate::test_faststart_detection` | reels | INT | nenhum | — |
| 701 | `reels/tests/test_validate.py::TestValidate::test_good_minimal_mp4` | reels | INT | nenhum | — |
| 702 | `reels/tests/test_validate.py::TestValidate::test_probe_fields` | reels | INT | nenhum | — |
| 703 | `reels/tests/test_validate.py::TestValidate::test_uniform_frame_detected` | reels | INT | nenhum | — |
| 704 | `reels/tests/test_validate.py::TestValidate::test_wrong_resolution_and_fps` | reels | INT | nenhum | — |
| 705 | `reels/tests/test_validate.py::TestValidateRejects::test_baseline_and_high_bitrate_rejected` | reels | INT | nenhum | — |
