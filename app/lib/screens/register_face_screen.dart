import 'dart:io';
import 'dart:typed_data';

import 'package:camera/camera.dart';
import 'package:flutter/material.dart';
import 'package:permission_handler/permission_handler.dart';

import '../config/tema.dart';
import '../services/api_client.dart';
import '../utils/formatters.dart';

/// Cadastro do rosto do usuário logado (o backend só guarda 1 rosto
/// por usuário, sempre associado ao dono do token JWT - por isso não
/// existe seletor de usuário aqui).
///
/// Esta tela tinha um visual próprio - ciano neon sobre quase-preto, fonte
/// Rajdhani, linha de scanner animada, moldura com cantos de mira. Ficava
/// bonita sozinha e destoava de todo o resto: era a única tela do app com
/// paleta e tipografia próprias, e vendia "scanner biométrico de filme"
/// numa ferramenta que a pessoa usa uma vez e esquece. O enquadramento
/// vertical aqui é o mesmo 3:4 que o leitor da porta usa - o app mostra
/// você do jeito que a porta vai te ver.
///
/// SÓ CÂMERA, de propósito. Existia aqui um "escolher da galeria", e ele
/// furava o sistema inteiro: o anti-spoofing do servidor reconhece foto de
/// tela e de papel, não distingue uma selfie digital normal de outra pessoa.
/// Qualquer um poderia cadastrar o rosto de um colega salvo no celular e
/// passar a receber a presença dele. A captura ao vivo é o que amarra o rosto
/// a quem está segurando o aparelho.
class RegisterFaceScreen extends StatefulWidget {
  const RegisterFaceScreen({super.key});

  @override
  State<RegisterFaceScreen> createState() => _RegisterFaceScreenState();
}

class _RegisterFaceScreenState extends State<RegisterFaceScreen> {
  // ── Estado ────────────────────────────────────────────────────
  bool _cadastrado = false;
  int _totalFotos = 0;
  String? _atualizadoEm;
  bool _statusLoading = true;

  CameraController? _camCtrl;
  List<CameraDescription> _cameras = [];
  bool _cameraReady = false;
  bool _isFrontCamera = true;
  bool _semPermissao = false;

  Uint8List? _capturedBytes;
  _UploadState _uploadState = _UploadState.idle;
  String? _errorMsg;

  @override
  void initState() {
    super.initState();
    _init();
  }

  Future<void> _init() async {
    await Future.wait([_initCamera(), _loadStatus()]);
  }

  Future<void> _loadStatus() async {
    setState(() => _statusLoading = true);
    try {
      final json = await ApiClient.get('/faces/status');
      final detalhe = json['detalhe'] as Map<String, dynamic>?;
      setState(() {
        _cadastrado = json['cadastrado'] == true;
        _totalFotos = (json['total'] as num?)?.toInt() ?? (_cadastrado ? 1 : 0);
        _atualizadoEm = detalhe?['atualizado_em']?.toString();
      });
    } catch (_) {
      // sem conexão / erro - mantém estado anterior
    } finally {
      if (mounted) setState(() => _statusLoading = false);
    }
  }

  Future<void> _initCamera() async {
    final status = await Permission.camera.request();
    if (!status.isGranted) {
      if (mounted) setState(() => _semPermissao = true);
      return;
    }

    _cameras = await availableCameras();
    if (_cameras.isEmpty) return;

    final desc = _cameras.firstWhere(
      (c) => c.lensDirection == CameraLensDirection.front,
      orElse: () => _cameras.first,
    );

    await _startCamera(desc);
  }

  Future<void> _startCamera(CameraDescription desc) async {
    await _camCtrl?.dispose();
    final ctrl = CameraController(desc, ResolutionPreset.high, enableAudio: false);
    await ctrl.initialize();
    if (!mounted) return;
    setState(() {
      _camCtrl = ctrl;
      _cameraReady = true;
    });
  }

  Future<void> _flipCamera() async {
    if (_cameras.length < 2) return;
    _isFrontCamera = !_isFrontCamera;
    final desc = _cameras.firstWhere(
      (c) =>
          c.lensDirection ==
          (_isFrontCamera ? CameraLensDirection.front : CameraLensDirection.back),
      orElse: () => _cameras.first,
    );
    setState(() => _cameraReady = false);
    await _startCamera(desc);
  }

  // ── Captura ───────────────────────────────────────────────────
  Future<void> _captureFromCamera() async {
    if (_camCtrl == null || !_cameraReady) return;
    try {
      final xfile = await _camCtrl!.takePicture();
      final bytes = await File(xfile.path).readAsBytes();
      setState(() {
        _capturedBytes = bytes;
        _uploadState = _UploadState.idle;
        _errorMsg = null;
      });
    } catch (e) {
      _showError('Erro ao capturar: $e');
    }
  }

  void _retake() => setState(() {
        _capturedBytes = null;
        _uploadState = _UploadState.idle;
        _errorMsg = null;
      });

  // ── Envio ─────────────────────────────────────────────────────
  Future<void> _registerFace() async {
    if (_capturedBytes == null) return;

    setState(() {
      _uploadState = _UploadState.loading;
      _errorMsg = null;
    });

    try {
      await ApiClient.postMultipart(
        '/faces',
        campoArquivo: 'foto',
        bytes: _capturedBytes!,
        nomeArquivo: 'rosto.jpg',
      );
      setState(() => _uploadState = _UploadState.success);
      await _loadStatus();
      await Future.delayed(const Duration(seconds: 2));
      if (mounted) _retake();
    } on ApiException catch (e) {
      setState(() {
        _uploadState = _UploadState.error;
        _errorMsg = e.mensagem;
      });
    } catch (e) {
      setState(() {
        _uploadState = _UploadState.error;
        _errorMsg = 'Erro inesperado: $e';
      });
    }
  }

  Future<void> _deleteFace() async {
    await ApiClient.delete('/faces');
    await _loadStatus();
  }

  void _showError(String msg) => setState(() => _errorMsg = msg);

  Future<void> _confirmDelete() async {
    final confirmado = await showDialog<bool>(
      context: context,
      builder: (_) => AlertDialog(
        title: const Text('Remover rosto?'),
        content: const Text(
          'A porta deixa de reconhecer você e sua presença passa a depender '
          'da lista manual. Dá pra cadastrar de novo quando quiser.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('Cancelar'),
          ),
          FilledButton(
            style: FilledButton.styleFrom(
              backgroundColor: CoresStatus.erro(context),
              minimumSize: const Size(0, 44),
            ),
            onPressed: () => Navigator.pop(context, true),
            child: const Text('Remover'),
          ),
        ],
      ),
    );
    if (confirmado == true) await _deleteFace();
  }

  @override
  void dispose() {
    _camCtrl?.dispose();
    super.dispose();
  }

  // ── Tela ──────────────────────────────────────────────────────
  @override
  Widget build(BuildContext context) {
    final revisando = _capturedBytes != null;

    return Scaffold(
      appBar: AppBar(
        title: const Text('Cadastro facial'),
        actions: [
          if (!revisando && _cameras.length > 1)
            IconButton(
              icon: const Icon(Icons.cameraswitch_outlined),
              tooltip: 'Virar câmera',
              onPressed: _flipCamera,
            ),
        ],
      ),
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.fromLTRB(20, 4, 20, 32),
          children: [
            _Visor(
              controller: _camCtrl,
              pronto: _cameraReady,
              semPermissao: _semPermissao,
              capturado: _capturedBytes,
              espelhar: _isFrontCamera,
            ),
            const SizedBox(height: 20),
            if (revisando) _areaConfirmar() else _areaCaptura(),
            if (_errorMsg != null) ...[
              const SizedBox(height: 16),
              _Recado(
                cor: CoresStatus.erro(context),
                rotulo: 'NÃO DEU CERTO',
                texto: _errorMsg!,
              ),
            ],
            if (_uploadState == _UploadState.success) ...[
              const SizedBox(height: 16),
              _Recado(
                cor: CoresStatus.ok(context),
                rotulo: 'CADASTRADO',
                texto: _totalFotos > 1
                    ? 'Agora são $_totalFotos fotos. Quanto mais variação de '
                        'luz e ângulo, melhor o reconhecimento.'
                    : 'A porta já reconhece você.',
              ),
            ],
            if (!_statusLoading) ...[
              const SizedBox(height: 32),
              _cartaoStatus(),
            ],
          ],
        ),
      ),
    );
  }

  Widget _areaCaptura() {
    final cores = Theme.of(context).colorScheme;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        // Dica curta e concreta. O reconhecimento compara vetores: rosto
        // centralizado e bem iluminado é o que separa um cadastro que
        // funciona de um que faz a porta hesitar.
        Text(
          'Olhe pra câmera com o rosto centralizado, num lugar bem iluminado '
          'e sem óculos escuros.',
          textAlign: TextAlign.center,
          style: TextStyle(color: cores.onSurfaceVariant, fontSize: 13.5, height: 1.45),
        ),
        const SizedBox(height: 18),
        FilledButton.icon(
          onPressed: _cameraReady ? _captureFromCamera : null,
          icon: const Icon(Icons.camera_alt_outlined, size: 19),
          label: const Text('Tirar foto'),
        ),
      ],
    );
  }

  Widget _areaConfirmar() {
    final enviando = _uploadState == _UploadState.loading;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        FilledButton(
          onPressed: enviando ? null : _registerFace,
          child: enviando
              ? const SizedBox(
                  height: 20,
                  width: 20,
                  child: CircularProgressIndicator(strokeWidth: 2),
                )
              : const Text('Usar esta foto'),
        ),
        const SizedBox(height: 10),
        TextButton(
          onPressed: enviando ? null : _retake,
          child: const Text('Tirar outra'),
        ),
        if (enviando) ...[
          const SizedBox(height: 6),
          Text(
            'Enviando pro servidor e extraindo as medidas do rosto. '
            'Pode levar alguns segundos.',
            textAlign: TextAlign.center,
            style: TextStyle(
              color: Theme.of(context).colorScheme.outline,
              fontSize: 12.5,
              height: 1.45,
            ),
          ),
        ],
      ],
    );
  }

  Widget _cartaoStatus() {
    final cores = Theme.of(context).colorScheme;
    final cor = _cadastrado ? CoresStatus.ok(context) : cores.outline;

    final quando = _atualizadoEm == null ? null : DateTime.tryParse(_atualizadoEm!);

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text('CADASTRO ATUAL', style: Tipos.etiqueta(context)),
        const SizedBox(height: 12),
        Row(
          children: [
            Container(
              width: 7,
              height: 7,
              decoration: BoxDecoration(color: cor, shape: BoxShape.circle),
            ),
            const SizedBox(width: 10),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    !_cadastrado
                        ? 'Nenhum rosto cadastrado'
                        : _totalFotos == 1
                            ? '1 foto cadastrada'
                            : '$_totalFotos fotos cadastradas',
                    style: const TextStyle(fontSize: 14.5, fontWeight: FontWeight.w500),
                  ),
                  if (quando != null) ...[
                    const SizedBox(height: 3),
                    Text(
                      formatarDataHora(quando.toLocal()),
                      style: Tipos.dado(context),
                    ),
                  ],
                ],
              ),
            ),
            if (_cadastrado)
              TextButton(
                onPressed: _confirmDelete,
                style: TextButton.styleFrom(foregroundColor: CoresStatus.erro(context)),
                child: const Text('Remover'),
              ),
          ],
        ),
      ],
    );
  }
}

/// Visor 3:4 - a mesma proporção de retrato que o leitor da porta recorta.
class _Visor extends StatelessWidget {
  final CameraController? controller;
  final bool pronto;
  final bool semPermissao;
  final Uint8List? capturado;
  final bool espelhar;

  const _Visor({
    required this.controller,
    required this.pronto,
    required this.semPermissao,
    required this.capturado,
    required this.espelhar,
  });

  @override
  Widget build(BuildContext context) {
    final cores = Theme.of(context).colorScheme;

    return ClipRRect(
      borderRadius: BorderRadius.circular(18),
      child: AspectRatio(
        aspectRatio: 3 / 4,
        child: ColoredBox(
          color: cores.surfaceContainerHighest,
          child: _conteudo(context),
        ),
      ),
    );
  }

  Widget _conteudo(BuildContext context) {
    if (capturado != null) {
      return Image.memory(capturado!, fit: BoxFit.cover);
    }

    if (semPermissao) {
      return const _Aviso(
        icone: Icons.no_photography_outlined,
        titulo: 'Sem acesso à câmera',
        texto: 'Autorize a câmera nas configurações do celular. O cadastro só '
            'aceita foto tirada na hora — é o que garante que o rosto é o seu.',
      );
    }

    if (!pronto || controller == null) {
      return const Center(child: CircularProgressIndicator());
    }

    // A prévia da frontal vem invertida em relação ao que a pessoa vê no
    // espelho; espelhar aqui é só conforto visual e não afeta o que é
    // enviado - o cadastro usa os bytes originais de takePicture().
    final preview = CameraPreview(controller!);
    return FittedBox(
      fit: BoxFit.cover,
      child: SizedBox(
        width: controller!.value.previewSize?.height ?? 1080,
        height: controller!.value.previewSize?.width ?? 1440,
        child: espelhar
            ? Transform(
                alignment: Alignment.center,
                transform: Matrix4.identity()..rotateY(3.1415926535),
                child: preview,
              )
            : preview,
      ),
    );
  }
}

class _Aviso extends StatelessWidget {
  final IconData icone;
  final String titulo;
  final String texto;

  const _Aviso({required this.icone, required this.titulo, required this.texto});

  @override
  Widget build(BuildContext context) {
    final cores = Theme.of(context).colorScheme;
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(28),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(icone, size: 26, color: cores.outline),
            const SizedBox(height: 14),
            Text(titulo, style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w500)),
            const SizedBox(height: 8),
            Text(
              texto,
              textAlign: TextAlign.center,
              style: TextStyle(color: cores.onSurfaceVariant, fontSize: 13, height: 1.45),
            ),
          ],
        ),
      ),
    );
  }
}

/// Faixa de resultado (deu certo / não deu), no mesmo vocabulário de cor
/// que o totem usa na porta.
class _Recado extends StatelessWidget {
  final Color cor;
  final String rotulo;
  final String texto;

  const _Recado({required this.cor, required this.rotulo, required this.texto});

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.fromLTRB(16, 12, 16, 14),
      decoration: BoxDecoration(
        color: CoresStatus.fundo(context, cor),
        borderRadius: BorderRadius.circular(12),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(rotulo, style: Tipos.etiqueta(context, cor: cor)),
          const SizedBox(height: 5),
          Text(
            texto,
            style: TextStyle(fontSize: 13.5, height: 1.4, color: cor),
          ),
        ],
      ),
    );
  }
}

enum _UploadState { idle, loading, success, error }
