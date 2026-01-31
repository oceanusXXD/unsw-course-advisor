export function useChatScroll(virtuosoRef) {
  return {
    scrollToBottom: () =>
      virtuosoRef.current?.scrollToIndex?.({ index: 'LAST', align: 'end', behavior: 'smooth' }),
  };
}
