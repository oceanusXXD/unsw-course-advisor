// src/components/LicensePanel.jsx
import React, { useState, useEffect } from 'react'
import {
    getMyLicense,
    activateLicense,
    decryptLicensedFile,
    validateLicense
} from '../../services/api'
export default function LicensePanel({ user, onClose }) {
    const [license, setLicense] = useState(null)
    const [loading, setLoading] = useState(true)
    const [activating, setActivating] = useState(false)
    const [deviceId, setDeviceId] = useState('')
    const [userKey, setUserKey] = useState(localStorage.getItem('user_key') || '')
    const [error, setError] = useState('')
    const [success, setSuccess] = useState('')

    // 测试相关状态
    const [testFileContent, setTestFileContent] = useState('');
    const [testResult, setTestResult] = useState(null)
    const [testing, setTesting] = useState(false)

    useEffect(() => {
        loadLicense()
        console.log(license)
    }, [])

    const loadLicense = async () => {
        setLoading(true)
        setError('')
        try {
            const data = await getMyLicense()
            setLicense(data.license)
        } catch (err) {
            setError(err.message)
        } finally {
            setLoading(false)
        }
    }

    const handleActivate = async (e) => {
        e.preventDefault();
        if (!deviceId.trim()) {
            setError('请输入设备ID');
            return;
        }

        setActivating(true);
        setError('');
        setSuccess('');

        try {
            const data = await activateLicense(deviceId.trim());
            console.log('[ACTIVATE RESPONSE]', data);

            if (data.user_key) {
                localStorage.setItem('user_key', data.user_key);
                setUserKey(data.user_key);
                console.log('[ACTIVATE] user_key(b64) length:', data.user_key.length);
            }

            // ✅ 修复：兼容直接返回 license 对象
            setLicense(data.license || data);

            // 使用 API 返回的消息
            setSuccess(data.message || '许可证激活成功！请务必保存 user_key');
        } catch (err) {
            setError(err.message);
        } finally {
            setActivating(false);
        }
    };


    const handleTestDecrypt = async (e) => {
        e.preventDefault();

        // 保留这些必要的本地输入检查
        if (!testFileContent.trim()) {
            setError('请输入文件内容');
            return;
        }
        if (!userKey) {
            setError('需要 user_key 才能解密，请先激活许可证');
            return;
        }
        if (!license || !license.license_key) {
            setError('需要 license_key 才能发起解密请求');
            return;
        }

        setTesting(true);
        setError('');
        setSuccess('');
        setTestResult(null);

        try {
            console.log('解析加密文件内容...');
            let encryptedData;
            try {
                encryptedData = JSON.parse(testFileContent.trim());
            } catch (err) {
                throw new Error('文件内容格式错误，请确保是合法的 JSON');
            }
            console.log('加密内容解析成功', encryptedData);

            console.log('开始完整的解密流程...');

            // ✅ 已删除多余的 authToken 检查

            const result = await decryptLicensedFile(
                encryptedData,         // 解析后的加密文件对象
                license.license_key,   // 用户的许可证密钥
                userKey                // 用户的 user_key (base64)
            );

            console.log('解密流程完成', result);

            setTestResult({
                message: '成功解密文件内容',
                data: result
            });
            setSuccess('解密测试成功！');

        } catch (err) {
            console.error('解密流程出错:', err);
            setError(`解密失败: ${err.message}`);
            setTestResult(null);
        } finally {
            setTesting(false);
        }
    };



    const copyToClipboard = (text) => {
        navigator.clipboard.writeText(text)
        setSuccess('已复制到剪贴板')
        setTimeout(() => setSuccess(''), 2000)
    }

    const formatDate = (dateString) => {
        if (!dateString) return '永久'
        const date = new Date(dateString)
        return date.toLocaleString('zh-CN')
    }

    const getDaysRemaining = (expiresAt) => {
        if (!expiresAt) return null
        const now = new Date()
        const expiry = new Date(expiresAt)
        const diff = expiry - now
        const days = Math.ceil(diff / (1000 * 60 * 60 * 24))
        return days
    }

    if (loading) {
        return (
            <div className="fixed inset-0 flex items-center justify-center bg-black/70 z-50">
                <div className="bg-gray-900 p-8 rounded-2xl">
                    <div className="animate-spin h-8 w-8 border-4 border-blue-500 border-t-transparent rounded-full" />
                </div>
            </div>
        )
    }

    const daysRemaining = license?.license_expires_at ? getDaysRemaining(license.license_expires_at) : null

    return (
        <div className="fixed inset-0 flex items-center justify-center bg-black/70 z-50 backdrop-blur-sm overflow-y-auto p-4">
            <div className="bg-gradient-to-br from-gray-900 to-gray-800 rounded-2xl w-full max-w-3xl shadow-2xl border border-gray-700 my-8">
                {/* Header */}
                <div className="flex justify-between items-center p-6 border-b border-gray-700">
                    <h2 className="text-2xl font-bold text-white">许可证管理</h2>
                    <button
                        onClick={onClose}
                        className="text-gray-400 hover:text-white transition-colors"
                    >
                        <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                        </svg>
                    </button>
                </div>

                <div className="p-6 space-y-6">
                    {/* 错误/成功提示 */}
                    {error && (
                        <div className="bg-red-500/10 border border-red-500/50 text-red-400 p-3 rounded-lg">
                            {error}
                        </div>
                    )}
                    {success && (
                        <div className="bg-green-500/10 border border-green-500/50 text-green-400 p-3 rounded-lg">
                            {success}
                        </div>
                    )}

                    {/* 许可证状态 */}
                    <div className="bg-gray-800/50 rounded-xl p-6 border border-gray-700">
                        <h3 className="text-lg font-semibold text-white mb-4">许可证状态</h3>

                        {license?.license_active ? (
                            <div className="space-y-3">
                                <div className="flex items-center gap-3">
                                    <div className="w-3 h-3 rounded-full bg-green-500 animate-pulse" />
                                    <span className="text-green-400 font-semibold">已激活</span>
                                </div>

                                <div className="grid grid-cols-2 gap-4 text-sm">
                                    <div>
                                        <p className="text-gray-400">许可证密钥</p>
                                        <div className="flex items-center gap-2 mt-1">
                                            <code className="text-blue-400 font-mono">{license.license_key}</code>
                                            <button
                                                onClick={() => copyToClipboard(license.license_key)}
                                                className="text-gray-400 hover:text-white transition-colors"
                                            >
                                                📋
                                            </button>
                                        </div>
                                    </div>

                                    <div>
                                        <p className="text-gray-400">设备ID</p>
                                        <p className="text-white mt-1">{license.device_id || '未绑定'}</p>
                                    </div>

                                    <div>
                                        <p className="text-gray-400">过期时间</p>
                                        <p className="text-white mt-1">{formatDate(license.license_expires_at)}</p>
                                    </div>

                                    <div>
                                        <p className="text-gray-400">剩余天数</p>
                                        <p className={`mt-1 font-semibold ${daysRemaining === null ? 'text-green-400' :
                                            daysRemaining > 30 ? 'text-green-400' :
                                                daysRemaining > 7 ? 'text-orange-400' : 'text-red-400'
                                            }`}>
                                            {daysRemaining === null ? '永久有效' : `${daysRemaining} 天`}
                                        </p>
                                    </div>
                                </div>

                                {/* User Key 显示 */}
                                {userKey && (
                                    <div className="mt-4 p-4 bg-yellow-500/10 border border-yellow-500/50 rounded-lg">
                                        <div className="flex items-start gap-2">
                                            <span className="text-yellow-500 text-xl">⚠️</span>
                                            <div className="flex-1">
                                                <p className="text-yellow-400 font-semibold mb-2">User Key（请妥善保存）</p>
                                                <div className="bg-gray-900 p-3 rounded font-mono text-xs text-gray-300 break-all">
                                                    {userKey}
                                                </div>
                                                <button
                                                    onClick={() => copyToClipboard(userKey)}
                                                    className="mt-2 text-sm text-yellow-400 hover:text-yellow-300 transition-colors"
                                                >
                                                    📋 复制 User Key
                                                </button>
                                            </div>
                                        </div>
                                    </div>
                                )}
                            </div>
                        ) : (
                            <div>
                                <div className="flex items-center gap-3 mb-4">
                                    <div className="w-3 h-3 rounded-full bg-gray-500" />
                                    <span className="text-gray-400">未激活</span>
                                </div>

                                {/* 激活表单 */}
                                <form onSubmit={handleActivate} className="space-y-4">
                                    <div>
                                        <label className="text-gray-300 text-sm font-medium block mb-2">
                                            设备ID（唯一标识）
                                        </label>
                                        <input
                                            type="text"
                                            value={deviceId}
                                            onChange={(e) => setDeviceId(e.target.value)}
                                            placeholder="例如: laptop-001"
                                            required
                                            className="w-full p-3 rounded-lg bg-gray-800/50 text-white border border-gray-600 focus:outline-none focus:border-blue-500 transition-colors"
                                        />
                                    </div>

                                    <button
                                        type="submit"
                                        disabled={activating}
                                        className="w-full bg-gradient-to-r from-blue-600 to-blue-700 hover:from-blue-700 hover:to-blue-800 disabled:from-gray-600 disabled:to-gray-700 text-white p-3 rounded-lg font-semibold transition-all duration-200 shadow-lg hover:shadow-blue-500/50 disabled:cursor-not-allowed"
                                    >
                                        {activating ? '激活中...' : '激活许可证'}
                                    </button>
                                </form>
                            </div>
                        )}
                    </div>

                    {/* 解密测试区域 */}
                    {(license && (license.license_active || license.license_key)) && (

                        <div className="bg-gray-800/50 rounded-xl p-6 border border-gray-700">
                            <h3 className="text-lg font-semibold text-white mb-4">🔐 解密测试</h3>

                            <form onSubmit={handleTestDecrypt} className="space-y-4">
                                <div>
                                    <label className="text-gray-300 text-sm font-medium block mb-2">
                                        粘贴要测试的文件内容
                                    </label>
                                    <textarea
                                        value={testFileContent}
                                        onChange={(e) => setTestFileContent(e.target.value)}
                                        placeholder="直接粘贴加密的文件内容(JSON格式)"
                                        className="w-full p-3 rounded-lg bg-gray-800/50 text-white border border-gray-600 focus:outline-none focus:border-blue-500 transition-colors"
                                        rows={6}
                                    />
                                </div>

                                {!userKey && (
                                    <div className="bg-orange-500/10 border border-orange-500/50 text-orange-400 p-3 rounded-lg text-sm">
                                        ⚠️ 需要 user_key 才能测试解密。请先激活许可证获取 user_key。
                                    </div>
                                )}

                                <button
                                    type="submit"
                                    disabled={testing || !userKey || !testFileContent.trim()}
                                    className="w-full bg-gradient-to-r from-purple-600 to-purple-700 hover:from-purple-700 hover:to-purple-800 disabled:from-gray-600 disabled:to-gray-700 text-white p-3 rounded-lg font-semibold transition-all duration-200 shadow-lg hover:shadow-purple-500/50 disabled:cursor-not-allowed"
                                >
                                    {testing ? '测试中...' : '测试解密'}
                                </button>
                            </form>

                            {/* 测试结果 */}
                            {testResult && (
                                <div className="mt-4 bg-gray-900 rounded-lg p-4 border border-gray-700">
                                    <div className="flex items-center gap-2 mb-3">
                                        <span className="text-green-400">✅</span>
                                        <h4 className="text-white font-semibold">测试结果</h4>
                                    </div>

                                    <div className="space-y-2 text-sm">
                                        <div>
                                            <span className="text-gray-400">步骤: </span>
                                            <span className="text-white">{testResult.step}</span>
                                        </div>
                                        <div>
                                            <span className="text-gray-400">状态: </span>
                                            <span className="text-green-400">{testResult.message}</span>
                                        </div>

                                        <details className="mt-3">
                                            <summary className="text-blue-400 cursor-pointer hover:text-blue-300">
                                                查看详细数据
                                            </summary>
                                            <pre className="mt-2 p-3 bg-black/50 rounded text-xs text-gray-300 overflow-x-auto">
                                                {JSON.stringify(testResult.data, null, 2)}
                                            </pre>
                                        </details>
                                    </div>
                                </div>
                            )}
                        </div>
                    )}

                    {/* 使用说明 */}
                    <div className="bg-blue-500/10 border border-blue-500/50 rounded-lg p-4">
                        <h4 className="text-blue-400 font-semibold mb-2">📘 使用说明</h4>
                        <ul className="text-sm text-gray-300 space-y-1">
                            <li>• 激活许可证后会生成唯一的 user_key，请务必保存</li>
                            <li>• user_key 用于解密文件，遗失无法恢复</li>
                            <li>• 可以使用"解密测试"功能验证许可证是否正常工作</li>
                            <li>• 许可证过期后无法获取新的文件解密密钥</li>
                        </ul>
                    </div>
                </div>
            </div>
        </div>
    )
}