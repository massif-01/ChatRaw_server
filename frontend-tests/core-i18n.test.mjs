import assert from 'node:assert/strict';
import fs from 'node:fs';
import test from 'node:test';

const appScript = fs.readFileSync('backend/static/app.js', 'utf8');
const appHtml = fs.readFileSync('backend/static/index.html', 'utf8');

test('core settings sections and task center use translation bindings', () => {
    for (const binding of [
        "t('users')",
        "t('modules')",
        "t('account')",
        "t('userManagement')",
        "t('featureSuites')",
        "t('moduleTask')",
        "t('approvalRequired')",
        "t('executionProcess')",
        "t('toolInput')",
        "t('toolResult')"
    ]) {
        assert.match(appHtml, new RegExp(binding.replace(/[()']/g, '\\$&')));
    }

    assert.doesNotMatch(appHtml, />User management</);
    assert.doesNotMatch(appHtml, />Feature suites</);
    assert.doesNotMatch(appHtml, />Change password</);
    assert.doesNotMatch(appHtml, />\s*Clear key\s*</);
    assert.doesNotMatch(appHtml, /\$\{artifact\.size\} bytes/);
    assert.doesNotMatch(appHtml, /alt="(?:User|AI)"/);
    assert.doesNotMatch(appHtml, /aria-label="(?:Settings navigation|Module tasks|Task progress)"/);
});

test('language selector remains in admin-only UI settings, not account settings', () => {
    const uiSection = appHtml.slice(
        appHtml.indexOf(`x-show="settingsTab === 'ui'"`),
        appHtml.indexOf(`x-show="settingsTab === 'users'"`)
    );
    const accountSection = appHtml.slice(
        appHtml.indexOf(`x-show="settingsTab === 'account'"`),
        appHtml.indexOf('<!-- Modal Actions Footer -->')
    );
    assert.match(
        appHtml,
        /<div class="nav-item" x-show="isAdmin\(\)"[^>]+settingsTab === 'ui'/
    );
    assert.match(uiSection, /setLanguage\('en'\)/);
    assert.match(uiSection, /setLanguage\('zh'\)/);
    assert.doesNotMatch(accountSection, /setLanguage\(/);
    assert.doesNotMatch(accountSection, /t\('language'\)/);
});

test('language changes synchronize storage and document metadata', () => {
    assert.match(appScript, /document\.documentElement\.lang = this\.lang === 'zh' \? 'zh-CN' : 'en'/);
    assert.match(appScript, /localStorage\.setItem\('justchat_lang', this\.lang\)/);
    assert.match(appScript, /this\.setLanguage\(this\.lang\)/);
});

test('known API errors are code-first and raw error text is not rendered', () => {
    for (const code of [
        'invalid_username_length',
        'username_in_use',
        'invalid_credentials',
        'current_password_incorrect',
        'last_active_admin'
    ]) {
        assert.match(appScript, new RegExp(`${code}:`));
    }
    assert.doesNotMatch(appScript, /showToast\(error\.message/);
    assert.doesNotMatch(appScript, /moduleTaskUi\.error = error\.message/);
    assert.doesNotMatch(appScript, /progressMessage = event\.data\.message/);
});

test('Chinese dictionary covers core account, module, and task surfaces', () => {
    for (const text of [
        "users: '用户'",
        "modules: '模块'",
        "account: '账户'",
        "featureSuites: '功能套件'",
        "approvalRequired: '需要审批'",
        "executionProcess: '执行过程'",
        "toolInput: '输入'",
        "toolResult: '结果'",
        "invalidCredentials: '用户名或密码错误'"
    ]) {
        assert.match(appScript, new RegExp(text.replace(/[()']/g, '\\$&')));
    }
});

test('module configuration performs a bounded readiness recheck', () => {
    assert.match(appScript, /await this\.recheckModuleAfterConfig\(moduleId\)/);
    assert.match(appScript, /const maxAttempts = 6/);
    assert.match(appScript, /module\.ready_status === 'ready'/);
    assert.match(appScript, /module\.config_status === 'missing'/);
    assert.doesNotMatch(
        appScript,
        /while\s*\(\s*module\.ready_status\s*!==\s*['"]ready['"]\s*\)/
    );
});

test('plugins can opt into the stable sidebar mount without DOM injection', () => {
    assert.match(appScript, /config\.placement === 'sidebar' \? 'sidebar' : 'toolbar'/);
    assert.match(appScript, /get sidebarPluginButtons\(\)/);
    assert.match(appHtml, /x-for="btn in sidebarPluginButtons"/);
    assert.match(appHtml, /class="plugin-sidebar-entry"/);
    assert.match(appHtml, /getSortedPluginButtons\('toolbar'\)/);
    assert.match(appHtml, /app\.min\.js\?v=7\.19/);
    assert.match(appHtml, /styles\.min\.css\?v=7\.12/);
    assert.match(appHtml, /content-security\.min\.js\?v=2/);
    assert.match(appScript, /if \(btn\.loading \|\| btn\.disabled\) return false/);
    assert.match(appHtml, /:disabled="btn\.loading \|\| btn\.disabled"/);
    assert.match(
        appHtml,
        /@click="handlePluginMoreButtonClick\(btn, \$refs\.pluginMoreButton\)"/
    );
});

test('unconfigured Resident entries stay hidden until their feature is visible', () => {
    assert.match(
        appScript,
        /\.filter\(integration => integration\.feature\?\.visible === true\)/
    );
    assert.match(appScript, /visible: false,\s+available: false,\s+state: 'hidden'/);
});
