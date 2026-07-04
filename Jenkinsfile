def FAILED_STAGE = "unknown"
def LOG_SNAPSHOT = [:]

pipeline {
    agent any

    triggers {
        GenericTrigger(
            genericVariables: [
                [key: 'ref', value: '$.ref']
            ],
            token: 'wpi',
            causeString: 'Triggered by GitHub Webhook via Smee',
            printContributedVariables: true,
            printPostContent: true,
            silentResponse: false
        )
        pollSCM('H/15 * * * *')
        cron('H 2 * * *')
    }

    parameters {
        booleanParam(
            name: 'has_github_auth',
            defaultValue: false,
            description: 'Use GitHub credentials (5000 req/h) and enable site deploy.'
        )
        booleanParam(
            name: 'update_site',
            defaultValue: false,
            description: 'Deploy updated index.html to GitHub Pages after successful build.'
        )
    }

    environment {
        UA              = "Mozilla/5.0_Windows_NT_10.0_Win64_x64"
        DL_DIR          = "tmp/downloads"
        LOG_FILE        = "repos/wpi_log.log"
        GITHUB_LIST     = "repos/github.txt"
        WEB_LIST        = "repos/web.txt"
        WPI_EOL_LINK    = "https://mega.nz/file/NZhwFZIA#GDWv3O8X_iSRw7_De67M2do8otRS-pnzdqFeWVHHCgk"
        WPI_SITE_REPO   = "Divopes/WPI-Site"
        MEGA_CREDS      = credentials('mega-account-creds')
    }

    stages {
        stage('Preparing') {
            steps {
                script {
                    FAILED_STAGE = 'Preparing'
                    echo "--- [INIT] Preparing workspace ---"
                    sh "mkdir -p ${env.DL_DIR} repos tmp"
                    sh "rm -rf ${env.DL_DIR}/*.new ${env.DL_DIR}/*.html tmp/*.json tmp/.has_updates"

                    if (!fileExists(env.LOG_FILE)) {
                        sh "touch ${env.LOG_FILE}"
                        echo "   [INIT] Created empty ${env.LOG_FILE}"
                    }

                    readFile(env.LOG_FILE).readLines().each { line ->
                        if (!line.trim() || line.startsWith('#')) return
                        def parts = line.split('\\|')
                        if (parts.size() >= 2 && !parts[0].startsWith('WEB')) {
                            LOG_SNAPSHOT[parts[0]] = parts[1]
                        }
                    }
                    echo "   [SNAPSHOT] Captured ${LOG_SNAPSHOT.size()} versions from log"
                }
            }
        }

        stage('Setup Dependencies') {
            steps {
                script {
                    FAILED_STAGE = 'Setup Dependencies'
                    def packages = ['genisoimage', 'curl', 'jq', 'wget', 'megatools', 'unzip']
                    def missing  = []

                    packages.each { pkg ->
                        def status = sh(script: "dpkg -s ${pkg} > /dev/null 2>&1 && echo ok || echo missing", returnStdout: true).trim()
                        if (status == 'missing') missing.add(pkg)
                    }

                    if (missing) {
                        echo "   [INSTALL] Missing: ${missing.join(', ')}"
                        sh "sudo apt-get update -qq"
                        sh "sudo apt-get install -y -qq ${missing.join(' ')}"
                    } else {
                        echo "   [SKIP] All packages present"
                    }
                }
            }
        }

        stage('Fetch All Software') {
            parallel {
                stage('Download Static (EoL)') {
                    steps {
                        script {
                            FAILED_STAGE = 'Download Static (EoL)'
                            def eolMarkerFile = "tmp/.eol_downloaded"
                            if (fileExists(eolMarkerFile)) {
                                echo "   [SKIP] EoL already downloaded (marker exists)"
                            } else {
                                echo ">>> [EOL] Downloading EoL package from Mega..."
                                timeout(time: 7, unit: 'MINUTES') {
                                    sh "megadl '${env.WPI_EOL_LINK}' --path tmp/"
                                }
                                def eolZip = sh(script: "ls tmp/*.zip 2>/dev/null | head -n 1", returnStdout: true).trim()
                                if (!eolZip) error "EOL zip not found"

                                sh "unzip -o '${eolZip}' -d '${env.DL_DIR}/'"
                                sh "rm -f '${eolZip}'"
                                sh "touch ${eolMarkerFile} tmp/.has_updates"
                                echo "   [OK] EoL extracted"
                            }
                        }
                    }
                }

                stage('Dynamic Updates') {
                    stages {
                    stage('Checking GitHub') {
                        steps {
                            script {
                                FAILED_STAGE = 'Checking GitHub'
                                echo "--- [GITHUB] Checking for updates ---"
                                if (!fileExists(env.GITHUB_LIST)) error "File not found!"

                                def lines    = readFile(env.GITHUB_LIST).readLines()
                                def logLines = readFile(env.LOG_FILE).readLines()

                                lines.each { line ->
                                    if (line.startsWith('#') || !line.trim()) return

                                    def parts = line.split(';')
                                    def url   = parts[0].trim()
                                    def regex = parts[1].trim()
                                    def repo  = url.replace("https://github.com/", "").replace(/\/$/, "")

                                    try {
                                        if (params.has_github_auth) {
                                            withCredentials([usernamePassword(credentialsId: 'github-creds', usernameVariable: 'GH_USR', passwordVariable: 'GH_PSW')]) {
                                                sh """curl -s -H "Authorization: Bearer \$GH_PSW" -H "Accept: application/vnd.github+json" "https://api.github.com/repos/${repo}/releases/latest" -o tmp/gh_response.json"""
                                            }
                                        } else {
                                            sh """curl -s -H "Accept: application/vnd.github+json" "https://api.github.com/repos/${repo}/releases/latest" -o tmp/gh_response.json"""
                                        }

                                        def jsonCheck = readFile("tmp/gh_response.json").trim()
                                        if (jsonCheck.contains("rate limit exceeded")) error "GITHUB RATE LIMIT EXCEEDED"

                                        def latestVersion = sh(script: "jq -r .tag_name tmp/gh_response.json", returnStdout: true).trim()
                                        if (!latestVersion || latestVersion == "null") error "Failed to get version"

                                        def isUpToDate = logLines.any { it.contains("${repo}|${latestVersion}|") }
                                        if (isUpToDate) {
                                            echo "   [SKIP] ${repo} already at ${latestVersion}"
                                            return
                                        }

                                        sh "touch tmp/.has_updates"
                                        echo "   [UPDATE] GitHub: ${repo} -> ${latestVersion}"

                                        sh """
                                            cd '${env.DL_DIR}' && ls -1 | grep -iE '${regex}' | xargs -I {} rm -rf "{}" || true
                                        """

                                        def downloadUrls = sh(script: """
                                            jq -r --arg REGEX "${regex}" '.assets[] | select(.name | test(\$REGEX; "i")) | .browser_download_url' tmp/gh_response.json
                                        """, returnStdout: true).trim()

                                        downloadUrls.split('\n').each { dUrl ->
                                            if (!dUrl.trim()) return
                                            def fileName = dUrl.split('/').last()
                                            sh "echo '   [DOWN] ${fileName}'"

                                            if (params.has_github_auth) {
                                                withCredentials([usernamePassword(credentialsId: 'github-creds', usernameVariable: 'GH_USR', passwordVariable: 'GH_PSW')]) {
                                                    sh """curl -L -s -H "Authorization: Bearer \$GH_PSW" -H "Accept: application/octet-stream" -o "${env.DL_DIR}/${fileName}" "${dUrl}" """
                                                }
                                            } else {
                                                sh "curl -L -s -o '${env.DL_DIR}/${fileName}' '${dUrl}'"
                                            }

                                            if (fileName.endsWith(".zip")) {
                                                def folderName = fileName.replace('.zip', '')
                                                sh "mkdir -p '${env.DL_DIR}/${folderName}'"
                                                sh "unzip -o '${env.DL_DIR}/${fileName}' -d '${env.DL_DIR}/${folderName}/'"
                                                sh "rm -f '${env.DL_DIR}/${fileName}'"
                                            }
                                        }

                                        logLines.removeAll { it.startsWith("${repo}|") }
                                        def dateNow = sh(script: "date +%Y-%m-%d", returnStdout: true).trim()
                                        logLines.add("${repo}|${latestVersion}|${dateNow}")
                                        writeFile file: env.LOG_FILE, text: logLines.join("\n") + "\n"
                                    } catch (Exception e) {
                                        sh "echo '=== RAW RESPONSE for ${repo} ===' && cat tmp/gh_response.json || echo '(file missing)'"
                                        currentBuild.result = 'UNSTABLE'
                                    }
                                }
                            }
                        }
                    }

                    // === ВОССТАНОВЛЕННЫЙ СТЕЙДЖ Checking Web ===
                    stage('Checking Web') {
                        steps {
                            script {
                                FAILED_STAGE = 'Checking Web'
                                echo "--- [WEB] Checking for updates ---"

                                def lines    = readFile(env.WEB_LIST).readLines()
                                def logLines = readFile(env.LOG_FILE).readLines()

                                lines.each { line ->
                                    if (line.startsWith('#') || !line.trim()) return
                                    try {
                                        def urls = []
                                        def mode = "HASH"

                                        if (line.contains("videolan.org")) {
                                            def v64 = sh(script: "curl -s https://download.videolan.org/pub/videolan/vlc/last/win64/ | grep -oP 'href=\"\\Kvlc-[0-9.]+-win64\\.exe' | head -n 1", returnStdout: true).trim()
                                            if (v64) urls.add("https://download.videolan.org/pub/videolan/vlc/last/win64/${v64}")
                                            def v32 = sh(script: "curl -s https://download.videolan.org/pub/videolan/vlc/last/win32/ | grep -oP 'href=\"\\Kvlc-[0-9.]+-win32\\.exe' | head -n 1", returnStdout: true).trim()
                                            if (v32) urls.add("https://download.videolan.org/pub/videolan/vlc/last/win32/${v32}")
                                            mode = "SMART"
                                        }
                                        else if (line.contains("telegram.org")) {
                                            def tg64 = sh(script: "curl -s -o /dev/null -w '%{redirect_url}' 'https://telegram.org/dl/desktop/win64'", returnStdout: true).trim()
                                            if (tg64) urls.add(tg64)
                                            def tg32 = sh(script: "curl -s -o /dev/null -w '%{redirect_url}' 'https://telegram.org/dl/desktop/win32'", returnStdout: true).trim()
                                            if (tg32) urls.add(tg32)
                                            mode = "SMART"
                                        }
                                        else if (line.contains("epicgames.com")) {
                                            def rawUrl = sh(script: "curl -s -A ${env.UA} -o /dev/null -w '%{redirect_url}' '${line}'", returnStdout: true).trim()
                                            if (rawUrl) { urls.add(rawUrl.split('\\?')[0]); mode = "SMART" }
                                        }
                                        else if (line.contains("mozilla.org")) {
                                            def rawUrl = sh(script: "curl -s -o /dev/null -w '%{redirect_url}' 'https://download.mozilla.org/?product=firefox-latest-ssl&os=win64&lang=ru'", returnStdout: true).trim()
                                            if (rawUrl) {
                                                def oldName = rawUrl.split('/').last()
                                                def newName = sh(script: "echo '${oldName}' | sed 's/%20/./g'", returnStdout: true).trim()
                                                urls.add("${rawUrl}?name=${newName}")
                                                mode = "SMART"
                                            }
                                        }
                                        else if (line.contains("fraps.com")) {
                                            def ver = sh(script: "curl -s https://fraps.com/download.php | grep -oP 'Fraps \\K[0-9.]+' | head -n 1", returnStdout: true).trim()
                                            if (ver) { urls.add("https://beepa.com/free/setup.exe?name=fraps-${ver}-setup.exe"); mode = "SMART" }
                                        }
                                        else if (line.contains("qbittorrent.org") || line.contains("hwinfo.com")) {
                                            def rssLink = line.contains("qbittorrent") ? "https://sourceforge.net/projects/qbittorrent/rss?path=/qbittorrent-win32" : "https://sourceforge.net/projects/hwinfo/rss"
                                            def webUrl = sh(script: "curl -s '${rssLink}' | grep -o 'https://[^\"<]*\\(x64_setup\\|hwi64_[0-9]\\+\\)\\.exe/download' | head -n 1", returnStdout: true).trim()
                                            if (webUrl) {
                                                sh "curl -L -s -A ${env.UA} -o 'tmp/sf_temp.html' '${webUrl}'"
                                                def directUrl = sh(script: "grep -oP 'https://downloads\\.sourceforge\\.net/[^\"]+' tmp/sf_temp.html | head -n 1", returnStdout: true).trim()
                                                sh "rm -f tmp/sf_temp.html"
                                                if (directUrl) {
                                                    def fName = webUrl.replace("/download", "").split('/').last()
                                                    if (line.contains("hwinfo")) fName = fName.replace(".exe", "").replace(".", "") + ".exe"
                                                    urls.add("${directUrl}?name=${fName}")
                                                    mode = "SMART"
                                                }
                                            }
                                        }
                                        else {
                                            urls.add(line.trim())
                                        }

                                        urls.each { dUrl ->
                                            if (!dUrl) return
                                            def cleanUrl = dUrl.contains("?name=") ? dUrl.split("\\?name=")[0] : dUrl
                                            def fname = dUrl.contains("?name=") ? dUrl.split("\\?name=")[1] : java.net.URLDecoder.decode(cleanUrl.split('/').last().split('\\?')[0], "UTF-8")
                                            if (fname == "client" || fname == "download" || fname == "") return

                                            def headers = "-A ${env.UA} -L"
                                            if (cleanUrl.contains("techpowerup.com")) headers += " -e 'https://www.techpowerup.com/'"

                                            if (mode == "SMART") {
                                                def inLog  = logLines.any { it.contains("|${fname}|") }
                                                def onDisk = fileExists("${env.DL_DIR}/${fname}")
                                                if (inLog && onDisk) {
                                                    echo "   [SKIP] Web: ${fname}"
                                                    return
                                                }
                                                sh "touch tmp/.has_updates"
                                                echo "   [DOWN] ${fname}"
                                                sh "curl -s ${headers} -o '${env.DL_DIR}/${fname}' '${cleanUrl}'"
                                                logLines.removeAll { it.contains("|${fname}|") }
                                                logLines.add("WEB-SMART|${fname}|" + sh(script: "date +%Y-%m-%d", returnStdout: true).trim())
                                            } else {
                                                sh "curl -s ${headers} -o '${env.DL_DIR}/${fname}.new' '${cleanUrl}'"
                                                def newHash = sh(script: "sha256sum '${env.DL_DIR}/${fname}.new' | awk '{print \$1}'", returnStdout: true).trim()
                                                def hashMatch = logLines.any { it.contains("|${fname}|${newHash}|") }
                                                if (hashMatch && fileExists("${env.DL_DIR}/${fname}")) {
                                                    echo "   [SKIP] Hash match: ${fname}"
                                                    sh "rm -f '${env.DL_DIR}/${fname}.new'"
                                                } else {
                                                    sh "touch tmp/.has_updates"
                                                    echo "   [UPDATE] Hash changed: ${fname}"
                                                    sh "mv '${env.DL_DIR}/${fname}.new' '${env.DL_DIR}/${fname}'"
                                                    logLines.removeAll { it.contains("|${fname}|") }
                                                    logLines.add("WEB-HASH|${fname}|${newHash}|" + sh(script: "date +%Y-%m-%d", returnStdout: true).trim())
                                                }
                                            }
                                            writeFile file: env.LOG_FILE, text: logLines.join("\n") + "\n"
                                        }
                                    } catch (Exception e) {
                                        echo "   [ERROR] ${line}: ${e.getMessage()}"
                                        currentBuild.result = 'UNSTABLE'
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }

        stage('Evaluate Updates') {
            steps {
                script {
                    FAILED_STAGE = 'Evaluate Updates'
                    if (!fileExists("tmp/.has_updates")) {
                        echo "--- [ABORT] No updates found in any source. Stopping pipeline to save resources. ---"
                        currentBuild.result = 'ABORTED'
                        currentBuild.description = 'ABORT_NO_UPDATES'
                        error("ABORT_NO_UPDATES: No updates found in any source.")
                    }
                    echo "--- [PROCEED] Updates detected. Proceeding with ISO generation. ---"
                }
            }
        }

        stage('Generate Config') {
            steps {
                script {
                    FAILED_STAGE = 'Generate Config'
                    sh "python3 tmp/gen_config.py"

                    // 👇 ДОБАВЛЕНО: Сохранение config.js как артефакта сборки 👇
                    archiveArtifacts artifacts: 'config.js', allowEmptyArchive: true
                    // 👆 =================================================== 👆
                }
            }
        }

        stage('Apply WPI Theme') {
            steps {
                script {
                    FAILED_STAGE = 'Apply WPI Theme'
                    echo "--- [THEME] Applying wpi_theme ---"
                    sh "rm -rf tmp/wpi_theme"
                    sh "git clone https://github.com/Divopes/wpi_theme.git tmp/wpi_theme"
                    sh "mkdir -p tmp/WPI/Themes/wpi_theme"
                    sh "cp -r tmp/wpi_theme/. tmp/WPI/Themes/wpi_theme/"
                    sh "rm -rf tmp/wpi_theme"
                    echo "   [OK] Theme copied to Themes/wpi_theme"

                    def themeFile = "tmp/WPI/UserFiles/themeoptions.js"
                    if (fileExists(themeFile)) {
                        def content = readFile(themeFile)
                        def updated = content.replaceAll(/'Win11'/, "'wpi_theme'")
                                             .replaceAll(/"Win11"/, '"wpi_theme"')
                        writeFile file: themeFile, text: updated
                        echo "   [OK] Theme set to wpi_theme in themeoptions.js"
                    } else {
                        echo "   [WARN] themeoptions.js not found at ${themeFile}"
                    }
                }
            }
        }

        stage('Distribute & Build ISO') {
            steps {
                script {
                    FAILED_STAGE = 'Distribute & Build ISO'
                    sh "rm -rf tmp/WPI && mkdir -p tmp/WPI"
                    sh "unzip -q WPI.zip -d tmp/WPI/ || unzip -q tmp/WPI.zip -d tmp/WPI/ || true"
                    sh "mkdir -p tmp/WPI/UserFiles tmp/WPI/Install"
                    sh "python3 tmp/gen_config.py"
                    sh "cp config.js tmp/WPI/UserFiles/"
                    def isoDate = sh(script: "date +%Y-%m-%d_%H-%M", returnStdout: true).trim()
                    env.ISO_NAME = "WPI_${isoDate}.iso"
                    sh "genisoimage -o tmp/${env.ISO_NAME} -V WPI -J -r -allow-multidot tmp/WPI"
                    env.ISO_SIZE = sh(script: "stat -c%s tmp/${env.ISO_NAME}", returnStdout: true).trim()
                    env.ISO_HASH = sh(script: "sha256sum tmp/${env.ISO_NAME} | awk '{print \$1}'", returnStdout: true).trim()
                }
            }
        }

        stage('Deploy to MEGA') {
            steps {
                script {
                    FAILED_STAGE = 'Deploy to MEGA'
                    withCredentials([usernamePassword(credentialsId: 'mega-account-creds', usernameVariable: 'U', passwordVariable: 'P')]) {
                        sh "megamkdir -u $U -p $P /Root/WPI 2>/dev/null || true"
                        sh "megaput -u $U -p $P --path /Root/WPI/ tmp/${env.ISO_NAME}"
                        env.MEGA_LINK = sh(script: "megals -u $U -p $P --export /Root/WPI/${env.ISO_NAME} | awk '{print \$1}'", returnStdout: true).trim()

                        sh """
                            OLDEST_ISO=\$(megals -u "\$U" -p "\$P" /Root/WPI/ | grep -i "\\.iso\$" | grep -v "${env.ISO_NAME}" | sort | head -n 1)
                            if [ -n "\$OLDEST_ISO" ]; then
                                megarm -u "\$U" -p "\$P" "\$OLDEST_ISO" || true
                            fi
                        """
                    }
                }
            }
        }

        stage('Update Site') {
            when { expression { return params.has_github_auth && params.update_site } }
            steps {
                script {
                    FAILED_STAGE = 'Update Site'

                def updatedApps = []

                    // GitHub-приложения
                    readFile(env.LOG_FILE).readLines().each { line ->
                        if (!line.trim() || line.startsWith('#')) return
                        def parts = line.split('\\|')
                        if (parts.size() >= 2 && !parts[0].startsWith('WEB')) {
                            def repo       = parts[0]
                            def newVersion = parts[1]
                            def oldVersion = LOG_SNAPSHOT[repo]
                            def appName    = repo.split('/').last()
                            if (oldVersion && oldVersion != newVersion)
                                updatedApps.add("<li>Обновлен ${appName} ${oldVersion} до ${newVersion}</li>")
                            else if (!oldVersion)
                                updatedApps.add("<li>Добавлен ${appName} ${newVersion}</li>")
                        }
                    }

                    // WEB-приложения
                    readFile(env.LOG_FILE).readLines().each { line ->
                        if (!line.trim() || line.startsWith('#')) return
                        def parts = line.split('\\|')
                        if (parts[0] == 'WEB-SMART' && parts.size() >= 3)
                            updatedApps.add("<li>Обновлен ${parts[1]}</li>")
                        else if (parts[0] == 'WEB-HASH' && parts.size() >= 4)
                            updatedApps.add("<li>Обновлен ${parts[1]}</li>")
                    }

                    def changelogHtml = updatedApps ? updatedApps.join('') : '<li>Обновления зависимостей и инфраструктуры</li>'
                    def dateDisplay = sh(script: "date +%d.%m.%Y", returnStdout: true).trim()

                    sh 'rm -rf tmp/site'
                    sh 'mkdir -p tmp/site'

                    dir('tmp/site') {
                        withCredentials([gitUsernamePassword(credentialsId: 'github-creds')]) {
                            sh "git clone -b main https://github.com/${env.WPI_SITE_REPO}.git ."
                        }
                        def html = readFile("index.html")

                        def gb = String.format(java.util.Locale.US, "%.1f GB", env.ISO_SIZE.toLong() / 1073741824.0)
                        html = html.replaceAll('href="https://mega\\.nz/[^"]*"', "href=\"${env.MEGA_LINK}\"")
                        html = html.replaceAll('[0-9]+(?:[,\\.][0-9]+)*\\s*GB', gb)

                        def verMatcher = java.util.regex.Pattern.compile('v\\.?(\\d+)\\.(\\d+)').matcher(html)
                        if (verMatcher.find()) {
                            def major = verMatcher.group(1).toInteger()
                            def minor = verMatcher.group(2).toInteger() + 1
                            env.WPI_VERSION = "v.${major}.${minor}"
                            html = html.replaceAll('v\\.?(\\d+)\\.(\\d+)', env.WPI_VERSION)
                        } else { env.WPI_VERSION = "v.1.0" }

                        html = html.replaceAll('\\d{2}\\.\\d{2}\\.\\d{4}', dateDisplay)

                        def shortHash = env.ISO_HASH.length() > 10 ? env.ISO_HASH.substring(0, 5) + "..." + env.ISO_HASH.substring(env.ISO_HASH.length() - 4) : "unknown"
                        html = java.util.regex.Pattern.compile('data-hash="[^"]*"').matcher(html).replaceAll(java.util.regex.Matcher.quoteReplacement("data-hash=\"${env.ISO_HASH}\""))
                        html = java.util.regex.Pattern.compile('(<span class="value">)[^<]*(</span>\\s*<button class="copy-btn" data-hash=)').matcher(html).replaceAll('$1' + shortHash + '$2')

                        def newChangelog = "<li>${env.WPI_VERSION} от ${dateDisplay}</li>${changelogHtml}"
                        html = java.util.regex.Pattern.compile('(showModal\\(\'Список изменений [^\']*\', \'<b>Что нового:</b><ul>)([^\']*)(</ul>)').matcher(html).replaceAll(java.util.regex.Matcher.quoteReplacement("showModal('Список изменений ${env.WPI_VERSION}', '<b>Что нового:</b><ul>${newChangelog}</ul>"))

                        writeFile file: "index.html", text: html

                        withCredentials([gitUsernamePassword(credentialsId: 'github-creds')]) {
                            sh """
                                git config user.email "jenkins@ci"
                                git config user.name "jenkins"
                                git add index.html
                                git commit -m "ci: ${env.WPI_VERSION} | ${dateDisplay} | ${gb}"
                                git push origin HEAD:main
                            """
                        }
                    }
                }
            }
        }
    }

    post {
        aborted {
            script {
                if (FAILED_STAGE == 'Evaluate Updates' || currentBuild.description?.contains('ABORT_NO_UPDATES')) {
                    def payload = """{
                      "embeds": [{
                        "title": "ℹ️ WPI Build Cancelled",
                        "color": 3447003,
                        "fields": [
                          { "name": "🏗 Build", "value": "#${env.BUILD_NUMBER}", "inline": true },
                          { "name": "ℹ️ Reason", "value": "No updates found in sources", "inline": true }
                        ],
                        "footer": { "text": "Jenkins CI • WPI Pipeline" }
                      }]
                    }"""
                    writeFile file: 'tmp/discord_abort.json', text: payload
                    withCredentials([string(credentialsId: 'discord-wpi-webhook', variable: 'DISCORD_WEBHOOK')]) {
                        sh 'curl -s -H "Content-Type: application/json" -d @tmp/discord_abort.json "$DISCORD_WEBHOOK" || true'
                    }
                } else {
                    def payload = """{
                      "embeds": [{
                        "title": "❌ WPI TIMEOUT / ABORTED",
                        "color": 15158332,
                        "fields": [
                          { "name": "🏗 Build",  "value": "#${env.BUILD_NUMBER}", "inline": true },
                          { "name": "💥 Stage", "value": "${FAILED_STAGE}", "inline": true },
                          { "name": "ℹ️ Reason", "value": "Timeout Exceeded or Manually Aborted", "inline": false },
                          { "name": "🔍 Logs",  "value": "${env.BUILD_URL}console", "inline": false }
                        ],
                        "footer": { "text": "Jenkins CI • WPI Pipeline" }
                      }]
                    }"""
                    writeFile file: 'tmp/discord_fail.json', text: payload
                    withCredentials([string(credentialsId: 'discord-wpi-webhook', variable: 'DISCORD_WEBHOOK')]) {
                        sh 'curl -s -H "Content-Type: application/json" -d @tmp/discord_fail.json "$DISCORD_WEBHOOK" || true'
                    }
                }
            }
        }
        success {
            script {
                def buildDuration = currentBuild.durationString.replace(' and counting', '')
                def siteField = (params.has_github_auth && params.update_site) ? "Updated to ${env.WPI_VERSION ?: 'n/a'}" : "Skipped"

                def discordUpdates = []
                // GitHub-приложения — сравниваем версии со снимком
                readFile(env.LOG_FILE).readLines().each { line ->
                    if (!line.trim() || line.startsWith('#')) return
                    def parts = line.split('\\|')
                    if (parts.size() >= 2 && !parts[0].startsWith('WEB')) {
                        def repo       = parts[0]
                        def newVersion = parts[1]
                        def oldVersion = LOG_SNAPSHOT[repo]
                        def appName    = repo.split('/').last()
                        if (!oldVersion || oldVersion != newVersion) {
                            discordUpdates.add("• " + (oldVersion ? "${appName}: ${oldVersion} -> ${newVersion}" : "${appName}: NEW ${newVersion}"))
                        }
                    }
                }

                readFile(env.LOG_FILE).readLines().each { line ->
                    if (!line.trim() || line.startsWith('#')) return
                    def parts = line.split('\\|')
                    if ((parts[0] == 'WEB-SMART' || parts[0] == 'WEB-HASH') && parts.size() >= 3) {
                        def fname = parts[1]
                            .replaceAll(/(?i)\.(exe|msi|zip)$/, '')   // убираем расширение
                            .replaceAll(/-[\d.]+$/, '')               // убираем -1.2.3 в конце
                            .replaceAll(/_[\d.]+$/, '')               // убираем _1.2.3 в конце
                            .replaceAll(/(?i)[\._-]x64$/, '')         // убираем архитектуру
                            .replaceAll(/(?i)[\._-]x86$/, '')         // убираем архитектуру
                            .replaceAll(/(?i)[\._-]setup$/, '')       // убираем -setup
                            .replaceAll(/(?i)setup$/, '')             // убираем setup в конце
                        def mode = parts[0] == 'WEB-HASH' ? 'web/hash' : 'web'
                        discordUpdates.add("• ${fname} (${mode})")
                    }
                }

                def lf = '\\n'
                def updatesText = discordUpdates ? discordUpdates.join(lf) : "No updates"

                def payload = """{
                  "embeds": [{
                    "title": "✅ WPI Build Complete",
                    "color": 3066993,
                    "fields": [
                      { "name": "📦 ISO", "value": "${env.ISO_NAME}", "inline": true },
                      { "name": "💾 Size", "value": "${String.format(java.util.Locale.US, '%.2f', env.ISO_SIZE.toLong() / 1073741824.0)} GB", "inline": true },
                      { "name": "⏱ Duration", "value": "${buildDuration}", "inline": true },
                      { "name": "🔗 Download", "value": "${env.MEGA_LINK ?: 'n/a'}", "inline": false },
                      { "name": "🔐 SHA256", "value": "${env.ISO_HASH ?: 'n/a'}", "inline": false },
                      { "name": "🌐 Site", "value": "${siteField}", "inline": true },
                      { "name": "📋 Updated Apps", "value": "${updatesText}", "inline": false }
                    ],
                    "footer": { "text": "Jenkins CI • Build #${env.BUILD_NUMBER}" }
                  }]
                }"""
                writeFile file: 'tmp/discord_ok.json', text: payload
                withCredentials([string(credentialsId: 'discord-wpi-webhook', variable: 'DISCORD_WEBHOOK')]) {
                    sh 'curl -s -H "Content-Type: application/json" -d @tmp/discord_ok.json "$DISCORD_WEBHOOK" || true'
                }

                sh "rm -rf tmp/WPI tmp/iso_out tmp/site tmp/*.json tmp/.has_updates gen_config.py config.js || true"
            }
        }
        failure {
            script {
                if (currentBuild.result == 'ABORTED' || currentBuild.result == 'NOT_BUILT') return

                def payload = """{
  "embeds": [{
    "title": "❌ WPI Build FAILED",
    "color": 15158332,
    "fields": [
      { "name": "🏗 Build",    "value": "#${env.BUILD_NUMBER}", "inline": true },
      { "name": "💥 Stage",   "value": "${FAILED_STAGE}",        "inline": false },
      { "name": "🔍 Logs",    "value": "${env.BUILD_URL}console","inline": false }
    ],
    "footer": { "text": "Jenkins CI • WPI Pipeline" }
  }]
}"""
                writeFile file: 'tmp/discord_fail.json', text: payload
                withCredentials([string(credentialsId: 'discord-wpi-webhook', variable: 'DISCORD_WEBHOOK')]) {
                    sh 'curl -s -H "Content-Type: application/json" -d @tmp/discord_fail.json "$DISCORD_WEBHOOK" || true'
                }
            }
        }
    }
}