//在后续的wps版本中，wps的所有枚举值都会通过wps.Enum对象来自动支持，现阶段先人工定义
var WPS_Enum = {
  msoCTPDockPositionLeft: 0,
  msoCTPDockPositionRight: 2
};

function GetUrlPath() {
  // 在本地网页的情况下获取路径
  if (window.location.protocol === 'file:') {
    const path = window.location.href;
    // 删除文件名以获取根路径
    return path.substring(0, path.lastIndexOf('/'));
  }

  // 在非本地网页的情况下获取根路径（包含 pathname 中的基础路径）
  const { protocol, hostname, port, pathname } = window.location;
  const portPart = port ? `:${port}` : '';
  // 去掉 pathname 末尾的文件名（如 index.html），保留目录部分
  const basePath = pathname.substring(0, pathname.lastIndexOf('/') + 1).replace(/\/+$/, '');
  return `${protocol}//${hostname}${portPart}${basePath}`;
}

function GetRouterHash() {
  if (window.location.protocol === 'file:') {
    return '';
  }

  return '/#';
}

export function showNativeMessage(message, title) {
  try {
    const assistant = window.Application?.Assistant;
    if (assistant?.DoAlert) {
      // Some WPS hosts expose DoAlert but return 0/undefined without opening
      // a dialog. Only a valid OK/close result means the message was shown.
      const result = assistant.DoAlert(title, message, 0, 0, 0, -1, true);
      if (result === 1 || result === 2) {
        return;
      }
    }
  } catch (error) {
    console.warn('[WPS] Native no-icon dialog unavailable:', error);
  }
  // WPS intercepts window.alert and displays its supported native dialog.
  window.alert(message);
}

export default {
  WPS_Enum,
  GetUrlPath,
  GetRouterHash
};
