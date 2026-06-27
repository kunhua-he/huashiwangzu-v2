const backendKeywordMap: [RegExp, string][] = [
  [/SQLSTATE/i, '系统内部错误'],
  [/exception/i, '系统内部错误'],
  [/syntax error/i, '系统内部错误'],
  [/Call to undefined/i, '系统内部错误'],
  [/stack trace/i, ''],
  [/#\d+\s+\/var\//i, ''],
  [/Undefined variable/i, '系统内部错误'],
  [/Division by zero/i, '系统内部错误'],
  [/Class not found/i, '系统内部错误'],
  [/RuntimeException/i, '系统内部错误'],
  [/QueryException/i, '数据查询出错'],
  [/InvalidArgumentException/i, '参数不对，请重试'],
  [/ModelNotFoundException/i, '内容不存在'],
]

export function friendlyErrorMessage(text: string): string {
  if (!text) return '系统开小差了，请稍后再试'
  for (const [regex, replacement] of backendKeywordMap) {
    if (regex.test(text)) return replacement || ''
  }
  return text
}
