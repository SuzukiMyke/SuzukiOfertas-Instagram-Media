# Exemplos fictícios do modo 1.1

Dados 100% fictícios (`.example`, imagem sintética de ruído). `exportacoes/A` e `exportacoes/B` têm cada uma o seu `manifest.json`.

```bash
python3 -m produtos --contrato 1.1 --dados produtos/exemplos_ficticios_v1_1/exportacoes \
  --decisoes produtos/exemplos_ficticios_v1_1/decisoes/decisoes.json \
  --permissoes produtos/exemplos_ficticios_v1_1/decisoes/permissoes_fotos.json \
  --termos produtos/exemplos_ficticios_v1_1/decisoes/termos_programas.json \
  --fotos-dir produtos/exemplos_ficticios_v1_1/fotos \
  --saida /tmp/saida_v11 --agora 2026-11-17T15:00:00Z
```
