import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart' show rootBundle;
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:provider/provider.dart';
import 'package:supabase_flutter/supabase_flutter.dart';

import 'config/app_config.dart';
import 'config/tema.dart';
import 'services/auth_provider.dart';
import 'services/configuracoes.dart';
import 'screens/login_screen.dart';
import 'screens/completar_cadastro_screen.dart';
import 'screens/home_screen.dart';

/// Jost e IBM Plex Mono são SIL Open Font License 1.1, que exige distribuir
/// o texto da licença junto do binário. Registrar aqui faz elas aparecerem
/// no "Ver licenças" padrão do Flutter - o mesmo lugar onde já aparecem as
/// dos pacotes.
void _registrarLicencasDasFontes() {
  LicenseRegistry.addLicense(() async* {
    for (final arquivo in ['OFL-Jost', 'OFL-IBMPlexMono']) {
      final texto = await rootBundle.loadString('assets/licencas/$arquivo.txt');
      yield LicenseEntryWithLineBreaks(['fontes'], texto);
    }
  });
}

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();

  _registrarLicencasDasFontes();

  // Antes do Supabase e do runApp: o endereço salvo precisa estar valendo
  // já no primeiro request, senão a tela inicial tenta o padrão compilado.
  await Configuracoes.carregar();

  await Supabase.initialize(
    url: AppConfig.supabaseUrl,
    // `anonKey` está deprecado e some numa major futura. A chave deste
    // projeto já é do formato novo (sb_publishable_...), então é
    // literalmente o parâmetro certo pra ela - não é só trocar o nome.
    publishableKey: AppConfig.supabaseAnonKey,
  );

  runApp(const FetinApp());
}

class FetinApp extends StatelessWidget {
  const FetinApp({super.key});

  @override
  Widget build(BuildContext context) {
    return ChangeNotifierProvider(
      create: (_) => AuthProvider(),
      child: MaterialApp(
        title: 'Fetin',
        debugShowCheckedModeBanner: false,
        // Os diálogos prontos do Material (showDatePicker, showTimePicker)
        // seguem o locale do app, não o texto que a gente escreve. Sem
        // declarar isto o app fica bilíngue sem querer: formulário em
        // português, calendário em inglês.
        //
        // Uma locale só, fixa: o app é de uma faculdade brasileira e as
        // strings estão todas em português no código. Deixar em
        // ThemeMode-style "system" faria o calendário virar espanhol num
        // celular em espanhol enquanto o resto continua em português.
        localizationsDelegates: const [
          GlobalMaterialLocalizations.delegate,
          GlobalWidgetsLocalizations.delegate,
          GlobalCupertinoLocalizations.delegate,
        ],
        supportedLocales: const [Locale('pt', 'BR')],
        locale: const Locale('pt', 'BR'),
        theme: temaFetin(Brightness.light),
        darkTheme: temaFetin(Brightness.dark),
        // Escuro sempre. Pra seguir a preferência do sistema (claro de dia,
        // escuro à noite), troque por ThemeMode.system.
        themeMode: ThemeMode.dark,
        home: const _AuthGate(),
      ),
    );
  }
}

/// Decide qual tela mostrar de acordo com o estado de autenticação.
/// Isso centraliza a navegação principal - as telas não precisam
/// saber pra onde ir depois de logar/completar cadastro/deslogar,
/// só chamam o método do AuthProvider e esse widget reage sozinho.
class _AuthGate extends StatelessWidget {
  const _AuthGate();

  @override
  Widget build(BuildContext context) {
    final status = context.watch<AuthProvider>().status;

    switch (status) {
      case AuthStatus.carregando:
        return const Scaffold(body: Center(child: CircularProgressIndicator()));
      case AuthStatus.deslogado:
        return const LoginScreen();
      case AuthStatus.logadoSemPerfil:
        return const CompletarCadastroScreen();
      case AuthStatus.logado:
        return const HomeScreen();
    }
  }
}
