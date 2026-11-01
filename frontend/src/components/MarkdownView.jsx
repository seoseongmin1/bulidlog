import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

const components = {
  table: (props) => (
    <div className="table-wrap">
      <table {...props} />
    </div>
  ),
};

/** 마크다운을 화면에 보여 준다. HTML은 해석하지 않으므로 AI 답변에 섞인 태그는 실행되지 않는다. */
export default function MarkdownView({ text }) {
  return (
    <div className="markdown">
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
        {text}
      </ReactMarkdown>
    </div>
  );
}
