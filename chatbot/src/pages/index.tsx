import { ChatProvider } from '../hooks/ChatContext';
import { ChatWindow } from '../components/ChatWindow';

export default function Home() {
  return (
    <ChatProvider>
      <ChatWindow />
    </ChatProvider>
  );
}