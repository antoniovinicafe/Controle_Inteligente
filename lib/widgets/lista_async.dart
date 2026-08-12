import 'package:flutter/material.dart';

import '../config/tema.dart';
import '../services/api_client.dart';
import '../services/configuracoes.dart';

/// Lista que resolve um Future e já trata os três estados chatos
/// (carregando / erro / vazio) do mesmo jeito em todas as telas,
/// com pull-to-refresh.
///
/// É StatefulWidget (não FutureBuilder direto no pai) de propósito: em
/// alguns casos (recarregar depois de voltar de outra tela via Navigator,
/// por exemplo) um FutureBuilder cujo `future` é só reatribuído pelo pai
/// pode ficar "preso" mostrando o snapshot antigo mesmo com um Future novo
/// sendo passado. Pra recarregar de fora com garantia, troque o `key`
/// (ex: `ValueKey(_versao)` incrementando `_versao`) - isso força o
/// Flutter a descartar e recriar este widget do zero, sem ambiguidade.
class ListaAsync<T> extends StatefulWidget {
  final Future<List<T>> Function() carregar;
  final Widget Function(BuildContext context, T item) itemBuilder;
  final String mensagemVazia;
  final IconData iconeVazio;

  /// Faixa opcional no topo, montada a partir da lista já carregada
  /// (ex: "2 das suas aulas foram canceladas"). Retorne null pra não
  /// mostrar nada.
  final Widget? Function(BuildContext context, List<T> itens)? cabecalho;

  /// Espaço extra no fim da lista pra o FAB não cobrir o último item.
  final bool reservarEspacoFab;

  const ListaAsync({
    super.key,
    required this.carregar,
    required this.itemBuilder,
    required this.mensagemVazia,
    this.iconeVazio = Icons.inbox_outlined,
    this.reservarEspacoFab = false,
    this.cabecalho,
  });

  @override
  State<ListaAsync<T>> createState() => _ListaAsyncState<T>();
}

class _ListaAsyncState<T> extends State<ListaAsync<T>> {
  late Future<List<T>> _future;

  @override
  void initState() {
    super.initState();
    _future = widget.carregar();
  }

  Future<void> _recarregar() async {
    final novo = widget.carregar();
    // CUIDADO: tem que ser bloco `{ }`, não arrow. `setState(() => _future =
    // novo)` retorna o próprio Future (o valor da atribuição), e o Flutter
    // tem um assert que rejeita callback de setState que devolve Future -
    // ele dispara ANTES do markNeedsBuild(), então o campo era atualizado
    // mas a tela nunca reconstruía. Era esse o bug que parecia "FutureBuilder
    // preso" e só aparece em debug (em release o assert nem roda).
    setState(() {
      _future = novo;
    });
    // RefreshIndicator usa o retorno daqui só pra saber quando esconder o
    // spinner - espera o fetch de verdade terminar (sucesso ou erro).
    await novo.catchError((_) => <T>[]);
  }

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<List<T>>(
      future: _future,
      builder: (context, snap) {
        if (snap.connectionState == ConnectionState.waiting) {
          return const Center(child: CircularProgressIndicator());
        }

        if (snap.hasError) {
          final falhaDeRede =
              snap.error is ApiException && (snap.error as ApiException).statusCode == 0;
          return _Centralizado(
            icone: Icons.cloud_off,
            rotulo: falhaDeRede ? 'SEM RESPOSTA' : 'ERRO DO SERVIDOR',
            corRotulo: CoresStatus.erro(context),
            titulo: 'Não foi possível carregar',
            subtitulo: snap.error is ApiException
                ? (snap.error as ApiException).mensagem
                : 'Verifique se o servidor está no ar e tente de novo.',
            // Quando a falha é de transporte, o motivo quase sempre é o
            // endereço - o IP da máquina muda sozinho quando o DHCP renova.
            // Mostrar pra quem foi que a gente ligou economiza a ida até os
            // ajustes só pra conferir.
            detalhe: falhaDeRede ? _hostAtual() : null,
            acao: FilledButton.tonalIcon(
              onPressed: _recarregar,
              icon: const Icon(Icons.refresh),
              label: const Text('Tentar de novo'),
            ),
          );
        }

        final itens = snap.data ?? const [];
        final topo = widget.cabecalho?.call(context, itens);

        return RefreshIndicator(
          onRefresh: _recarregar,
          child: itens.isEmpty
              ? ListView(
                  physics: const AlwaysScrollableScrollPhysics(),
                  children: [
                    if (topo != null) topo,
                    SizedBox(height: MediaQuery.of(context).size.height * 0.25),
                    _Centralizado(icone: widget.iconeVazio, titulo: widget.mensagemVazia),
                  ],
                )
              : ListView.separated(
                  physics: const AlwaysScrollableScrollPhysics(),
                  padding: EdgeInsets.only(
                    top: 8,
                    bottom: widget.reservarEspacoFab ? 88 : 8,
                  ),
                  itemCount: itens.length + (topo != null ? 1 : 0),
                  // Fio só entre itens, e nunca embaixo do cabeçalho: ele é
                  // um bloco à parte, não o primeiro da lista.
                  separatorBuilder: (context, i) =>
                      (topo != null && i == 0) ? const SizedBox.shrink() : const _Fio(),
                  itemBuilder: (context, i) {
                    if (topo != null) {
                      if (i == 0) return topo;
                      return widget.itemBuilder(context, itens[i - 1]);
                    }
                    return widget.itemBuilder(context, itens[i]);
                  },
                ),
        );
      },
    );
  }
}

/// Divisória recuada. Começa depois da margem do texto pra a lista ler como
/// uma coluna contínua, e não como uma pilha de faixas empilhadas.
class _Fio extends StatelessWidget {
  const _Fio();

  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.only(left: 16),
        child: Divider(
          height: 1,
          color: Theme.of(context).colorScheme.outlineVariant.withValues(
                alpha: Theme.of(context).brightness == Brightness.dark ? 0.16 : 0.5,
              ),
        ),
      );
}

/// Só o "host:porta" do endereço da API - sem esquema nem sufixo /api, que
/// são ruído pra quem só quer conferir se está falando com a máquina certa.
String _hostAtual() {
  final uri = Uri.tryParse(Configuracoes.apiBaseUrl);
  if (uri == null || uri.host.isEmpty) return Configuracoes.apiBaseUrl;
  return uri.hasPort ? '${uri.host}:${uri.port}' : uri.host;
}

/// Estado de lista vazia ou com falha.
///
/// O ícone gigante centralizado que estava aqui é o desenho padrão de tela
/// vazia em qualquer app - e ocupava o espaço todo dizendo nada. Agora quem
/// nomeia o estado é a etiqueta monoespaçada (a voz da máquina), o ícone
/// vira uma marca pequena ao lado dela, e sobra espaço pro que importa: o
/// que aconteceu e o que fazer a respeito.
class _Centralizado extends StatelessWidget {
  final IconData icone;
  final String titulo;
  final String? subtitulo;

  /// Nome do estado em caixa alta ("SEM RESPOSTA"). Sem isso a etiqueta
  /// some e sobra só o ícone - o certo pra uma lista que está vazia por
  /// motivo nenhum, sem nada de errado.
  final String? rotulo;
  final Color? corRotulo;

  /// Linha monoespaçada no rodapé (o endereço que o app tentou alcançar).
  final String? detalhe;

  final Widget? acao;

  const _Centralizado({
    required this.icone,
    required this.titulo,
    this.subtitulo,
    this.rotulo,
    this.corRotulo,
    this.detalhe,
    this.acao,
  });

  @override
  Widget build(BuildContext context) {
    final cores = Theme.of(context).colorScheme;
    final tomRotulo = corRotulo ?? cores.outline;

    return Center(
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 40, vertical: 32),
        child: ConstrainedBox(
          // Linha curta lê mais rápido e impede que a mensagem de erro
          // atravesse a tela inteira num tablet.
          constraints: const BoxConstraints(maxWidth: 340),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Icon(icone, size: 15, color: tomRotulo),
                  const SizedBox(width: 8),
                  Text(
                    rotulo ?? 'VAZIO',
                    style: Tipos.etiqueta(context, cor: tomRotulo),
                  ),
                ],
              ),
              const SizedBox(height: 14),
              Text(
                titulo,
                textAlign: TextAlign.center,
                style: Theme.of(context).textTheme.titleMedium?.copyWith(
                      fontWeight: FontWeight.w500,
                    ),
              ),
              if (subtitulo != null) ...[
                const SizedBox(height: 8),
                Text(
                  subtitulo!,
                  textAlign: TextAlign.center,
                  style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                        color: cores.onSurfaceVariant,
                        height: 1.4,
                      ),
                ),
              ],
              if (detalhe != null) ...[
                const SizedBox(height: 14),
                Text(detalhe!, style: Tipos.dado(context)),
              ],
              if (acao != null) ...[
                const SizedBox(height: 22),
                acao!,
              ],
            ],
          ),
        ),
      ),
    );
  }
}

/// Atalho pra mostrar erro de ação (não de carregamento) num SnackBar.
void mostrarErro(BuildContext context, Object erro) {
  final msg = erro is ApiException ? erro.mensagem : 'Erro inesperado: $erro';
  ScaffoldMessenger.of(context).showSnackBar(
    SnackBar(content: Text(msg), backgroundColor: Theme.of(context).colorScheme.error),
  );
}

void mostrarOk(BuildContext context, String msg) {
  ScaffoldMessenger.of(context)
      .showSnackBar(SnackBar(content: Text(msg)));
}
