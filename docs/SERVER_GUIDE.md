# サーバー担当者向け

対象：NaChatを設置・運用する担当者。社員のPCにはDockerを入れず、サーバー側でまとめて動かします。社員アカウントの日常管理は[アカウント管理者向け](ADMIN_GUIDE.md)を参照してください。

## 設置前に用意するもの

- 常時稼働するLinuxホスト（初期対象はlinux/amd64）。WindowsのDocker Desktop（Linuxコンテナ）でも試用できます。[Windows導入手順](../Windows社内テスト手順.txt)を参照。
- Docker EngineとDocker Compose。LAN用設定にはCompose 2.24.4以上が必要。
- NaChatの配布一式、固定IPまたは接続ホスト名、クライアントが信頼するHTTPS証明書。IPで接続する場合は社内DNSは不要です。
- データ保存用SSDと、別ホストに保管するバックアップ先。
- アカウント管理者、運用担当、障害時の連絡先。

4コア・メモリ8GBは初期検証の目安です。添付容量と実際の同時利用で調整してください。ホストのスリープを無効にし、Dockerを自動起動する設定にします。

以下のコマンドは配布物のcompose.yamlがあるフォルダで実行します。

## 配布物から設置する

1. 配布一式をホストへコピーします。images.tarだけでなく、Compose設定、infra、docsも必要です。
2. イメージを読み込みます。

    docker load -i images.tar

3. .env.exampleを.envへコピーします。SECRET_KEYとPOSTGRES_PASSWORDは、それぞれ十分長いランダム値へ変更してください。実値は共有資料やソース管理に入れません。
4. ホスト内だけで起動を確認する場合は、次を実行します。

    docker compose up -d --no-build --pull never

5. 最初の管理者を対話形式で作成します。

    docker compose exec app python manage.py bootstrap

この操作はユーザーがいない新規環境だけで使います。ログインIDと初期パスワードがともに administorator、表示名が「管理者」のアカウントを作成します。既存環境を移す場合は新規作成せず、バックアップを復元します。

ホスト内の確認URLは http://localhost:8080 です。この標準設定では別PCから接続できません。Python・Node.js・PostgreSQLをホストに個別インストールする必要はありません。

## 社内の別PCから接続できるようにする

1. 固定IPを確保するか、社内DNSへホスト名を登録します。IPで接続する場合は、そのIPを証明書のSANへ含め、以下の設定例のホスト名もIPに置き換えます。以下のchat.example.internalは例です。実際の社内ホスト名に置き換えてください。
2. certs/server.crtとcerts/server.keyへ証明書と秘密鍵を配置し、秘密鍵のアクセスを制限します。社内CAの場合、社員PC側でもそのCAを信頼する設定が必要です。
3. .envを設定します。

    ALLOWED_HOSTS=localhost,127.0.0.1,chat.example.internal
    ORIGINS=https://chat.example.internal
    SECURE_COOKIES=1

localhostはヘルスチェック用に残します。

4. LAN用設定で起動します。

    docker compose -f compose.yaml -f compose.lan.yaml up -d --no-build --pull never

5. ホストのファイアウォールで443を社内LANからのみ許可します。DB・Redisのポートは公開しません。
6. 別PCから https://chat.example.internal を開き、ログイン・投稿・添付・再接続を確認します。
7. アカウント管理者へURLと初期ログイン情報を渡し、社員用アカウントの発行を依頼します。

LAN用設定はlocalhostのHTTPポートをHTTPSへ置き換えます。社員にlocalhostのURLを案内しないでください。現地のDNS・証明書・ファイアウォール設定と、別Linuxホストへの移設は導入先での検証が必要です。

## 日常の起動・停止・状態確認

社内LAN運用では、常に両方のComposeファイルを指定します。

    docker compose -f compose.yaml -f compose.lan.yaml ps
    docker compose -f compose.yaml -f compose.lan.yaml logs --tail 100 app
    docker compose -f compose.yaml -f compose.lan.yaml stop
    docker compose -f compose.yaml -f compose.lan.yaml up -d --no-build --pull never

このPC内だけの試用環境では「-f compose.yaml -f compose.lan.yaml」を省略できます。通常の停止で「down -v」は使用しないでください。データボリュームも削除されます。

## バックアップ

アプリへの書き込みを一時停止してDBと添付を揃えて取得します。停止時間を利用者へ案内し、完了後はアクセスを確認します。

Linux:

    bash infra/backup.sh

Windows PowerShell:

    ./infra/backup.ps1

backups/日時/にDBと添付が保存されます。別ホストへ複製してください。.env、証明書、秘密鍵は別途安全に保管します。Dockerイメージには会話データは含まれません。

LAN運用でスクリプトを使う場合は、使用するシェルでCOMPOSE_FILEに両方のファイルを指定してください。スクリプト内部のCompose操作にも設定が引き継がれます。

Linux:

    export COMPOSE_FILE=compose.yaml:compose.lan.yaml
    bash infra/backup.sh

PowerShell:

    $env:COMPOSE_FILE='compose.yaml;compose.lan.yaml'
    ./infra/backup.ps1

バックアップ頻度は、何時間分まで失ってよいかと、どれだけの停止時間を許容できるかを社内で決めて設定します。定期バックアップの自動実行は別途設定が必要です。

## 復元・移設

本番データを上書きせず、空の別Composeプロジェクトへ復元します。

Linux:

    COMPOSE_PROJECT_NAME=nachat-restore bash infra/restore.sh /absolute/path/to/backup

PowerShell:

    ./infra/restore.ps1 -BackupDirectory C:/backup/日時 -RestoreProject nachat-restore

復元先のDBが空でなければスクリプトは拒否します。復元後、同じホストで試す場合は本番と衝突しないポートを割り当て、履歴・添付・権限・ログインを確認します。確認後に接続先を切り替えてください。イメージ読み込みだけではデータは移りません。

## 更新する

1. バックアップと復元手順を確認し、停止時間を案内します。
2. 保守担当者から受け取ったイメージと設定・更新手順を確認します。
3. 新しいイメージをdocker loadで読み込みます。
4. LAN用の両Composeファイルを指定してupを実行します。DBの準備完了後、マイグレーションが成功してからアプリが起動します。
5. ログイン、投稿、過去の添付を確認します。

DBに互換性のない変更がある場合、古いイメージに戻すだけでは復旧できません。別環境へのバックアップ復元を含めた手順を保守担当者から受け取ってください。

## 管理者の追加・復旧

管理者を追加する場合:

    docker compose exec app python manage.py createsuperuser

最初に作成した管理者がパスワードを忘れた場合:

    docker compose exec app python manage.py changepassword 管理者のメール

LAN運用では上記にも両Composeファイルの指定を付けます。ホスト管理権限を持つ担当者だけが実行してください。パスワード変更後、以前のログイン状態は失効します。

## 障害時の確認

| 症状 | 確認すること |
|---|---|
| 全員が開けない | ホスト電源、Docker、コンテナ状態、DNS、証明書、ファイアウォール |
| 1人だけログイン不可 | アカウント管理者へ有効状態とパスワード確認を依頼 |
| 新着が届かない | app・redisの状態、ブラウザの接続表示、アプリログ |
| 添付や投稿が失敗 | 空きディスク容量、添付上限、app・dbのログ |
| 再起動後に復帰しない | Dockerの自動起動、コンテナの起動・ヘルスチェック |

## 保存・閲覧の現行仕様

- 管理者の画面権限と、DBを直接操作できるホスト管理権限は別です。
- 投稿削除後は本文を消して行を保持します。添付はアクセス不可になりますが保存領域に残ります。バックアップ内の過去データも残ります。
- ユーザー管理、パスワード変更、メンバー操作はAuditテーブルへ記録します。編集前の本文は保存しません。
- 古い変更記録や未使用添付の自動清掃は未実装です。容量監視、保存期間、監査方針を運用開始前に決めてください。

[入口へ戻る](../README.md)

## ログイン履歴の確認

ログイン成功・認証失敗・試行回数制限をDBに保存します。日時、入力されたアカウント、成功時のユーザーID・表示名・登録メール、接続元IP、ブラウザ情報（User-Agent）を記録します。パスワード・Cookie・セッションIDは記録しません。入力アカウントは254文字、ブラウザ情報は512文字までです。

最近100件を新しい順に表示（日時は日本時間）：

    docker compose exec -T app python manage.py login_logs

アカウントを絞り込む場合：

    docker compose exec -T app python manage.py login_logs --account administorator --limit 200

1行1件のJSON形式です。結果は success / failed / rate_limited。ログはサーバー担当者が確認します。管理者は設定画面の「ログイン履歴」タブでも閲覧・絞り込みできます。一般社員は閲覧できません。DBバックアップに含まれ、現在は自動削除しません。過去のログインは遡って復元できません。CSRF拒否など、ログイン処理に到達しないリクエストはこの履歴の対象外です。

IPはnginxが直接受け取った接続元を記録します。アプリの8000番ポートを直接公開せず、必ず付属のnginxを経由してください。外部から送られたIPヘッダーはnginxで上書きします。Docker DesktopやVPN・NAT経由では共通のIPになることがあるため、社内の別PCから実際の記録を確認してください。ブラウザ情報は端末の自己申告で、端末本人の証明にはなりません。

プロフィール画像はmediaボリュームのavatarsフォルダーに保存されます。既存のバックアップ（database.dump＋media.tar.gz）に含まれ、追加のバックアップ操作は不要です。
