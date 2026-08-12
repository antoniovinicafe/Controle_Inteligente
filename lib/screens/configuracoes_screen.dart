import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;

import '../config/tema.dart';
import '../services/configuracoes.dart';
import '../widgets/lista_async.dart' show mostrarOk;

/// Onde apontar o app quando o servidor muda de endereço.
///
/// O botão de testar existe porque salvar um endereço errado não dá erro
/// na hora - o app só passa a falhar depois, em telas aleatórias, com
/// "não foi possível conectar". Testar antes transforma isso num
/// diagnóstico de dois segundos.
class ConfiguracoesScreen extends StatefulWidget {
  const ConfiguracoesScreen({super.key});

  @override
  State<ConfiguracoesScreen> createState() => _ConfiguracoesScreenState();
}

class _ConfiguracoesScreenState extends State<ConfiguracoesScreen> {
  late final TextEditingController _campo =
      TextEditingController(text: Configuracoes.apiBaseUrl);

  bool _testando = false;
  bool? _alcancavel;
  String? _detalhe;

  @override
  void dispose() {
    _campo.dispose();
    super.dispose();
  }

  Future<void> _testar() async {
    final url = Configuracoes.normalizar(_campo.text);
    setState(() {
      _testando = true;
      _alcancavel = null;
      _detalhe = null;
    });

    try {
      // Vai direto no http, sem o ApiClient: aqui a gente testa um
      // endereço candidato, que ainda não é o que o app usa.
      final r = await http
          .get(Uri.parse('$url/health'))
          .timeout(const Duration(seconds: 6));
      final ok = r.statusCode == 200 &&
          (jsonDecode(r.body) as Map)['status'] == 'ok';
      setState(() {
        _alcancavel = ok;
        _detalhe = ok
            ? 'Servidor respondeu em $url'
            : 'Respondeu, mas não parece ser o servidor do Fetin (HTTP ${r.statusCode})';
      });
    } catch (e) {
      setState(() {
        _alcancavel = false;
        _detalhe = 'Sem resposta. Confira se o PC e o celular estão no '
            'mesmo Wi-Fi e se o servidor está rodando.';
      });
    } finally {
      if (mounted) setState(() => _testando = false);
    }
  }

  Future<void> _salvar() async {
    await Configuracoes.definirApiBaseUrl(_campo.text);
    if (!mounted) return;
    _campo.text = Configuracoes.apiBaseUrl;
    mostrarOk(context, 'Endereço salvo');
    setState(() {});
  }

  Future<void> _restaurar() async {
    await Configuracoes.restaurarPadrao();
    if (!mounted) return;
    _campo.text = Configuracoes.apiBaseUrl;
    setState(() {
      _alcancavel = null;
      _detalhe = null;
    });
  }

  @override
  Widget build(BuildContext context) {
    final cores = Theme.of(context).colorScheme;

    return Scaffold(
      appBar: AppBar(title: const Text('Ajustes')),
      body: ListView(
        padding: const EdgeInsets.all(20),
        children: [
          Text('Servidor', style: Theme.of(context).textTheme.titleMedium),
          const SizedBox(height: 6),
          Text(
            'Endereço do servidor Fetin na rede. Mude aqui quando o IP do '
            'computador trocar — não precisa reinstalar o app.',
            style: TextStyle(color: cores.onSurfaceVariant, fontSize: 13.5),
          ),
          const SizedBox(height: 20),
          TextField(
            controller: _campo,
            autocorrect: false,
            keyboardType: TextInputType.url,
            // Endereço de rede é dado de máquina: mono evita confundir
            // 0 com O e 1 com l na hora de digitar um IP.
            style: Tipos.dado(context, tamanho: 15, cor: cores.onSurface),
            decoration: const InputDecoration(
              labelText: 'Endereço',
              hintText: '192.168.0.10:5000',
            ),
          ),
          const SizedBox(height: 8),
          Text(
            'Pode digitar só o IP e a porta — o resto é completado.',
            style: TextStyle(color: cores.outline, fontSize: 12.5),
          ),
          const SizedBox(height: 20),
          Row(
            children: [
              Expanded(
                child: OutlinedButton.icon(
                  onPressed: _testando ? null : _testar,
                  icon: _testando
                      ? const SizedBox(
                          width: 16,
                          height: 16,
                          child: CircularProgressIndicator(strokeWidth: 2),
                        )
                      : const Icon(Icons.wifi_find),
                  label: const Text('Testar'),
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: FilledButton(
                  onPressed: _salvar,
                  child: const Text('Salvar'),
                ),
              ),
            ],
          ),
          if (_detalhe != null) ...[
            const SizedBox(height: 18),
            _Resultado(ok: _alcancavel == true, texto: _detalhe!),
          ],
          const SizedBox(height: 28),
          Divider(color: cores.outlineVariant),
          const SizedBox(height: 12),
          Row(
            children: [
              Expanded(
                child: Text(
                  Configuracoes.personalizado
                      ? 'Usando um endereço personalizado.'
                      : 'Usando o endereço padrão do aplicativo.',
                  style: TextStyle(color: cores.onSurfaceVariant, fontSize: 13),
                ),
              ),
              if (Configuracoes.personalizado)
                TextButton(
                  onPressed: _restaurar,
                  child: const Text('Restaurar'),
                ),
            ],
          ),
          const SizedBox(height: 6),
          Text(
            'Padrão: ${Configuracoes.padraoDeFabrica}',
            style: Tipos.dado(context, tamanho: 11.5),
          ),
        ],
      ),
    );
  }
}

class _Resultado extends StatelessWidget {
  final bool ok;
  final String texto;

  const _Resultado({required this.ok, required this.texto});

  @override
  Widget build(BuildContext context) {
    final cor = ok ? CoresStatus.ok(context) : CoresStatus.erro(context);
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: CoresStatus.fundo(context, cor),
        borderRadius: BorderRadius.circular(12),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(ok ? Icons.check_circle_outline : Icons.error_outline,
              color: cor, size: 20),
          const SizedBox(width: 10),
          Expanded(
            child: Text(texto, style: TextStyle(color: cor, fontSize: 13.5)),
          ),
        ],
      ),
    );
  }
}
