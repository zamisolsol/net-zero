import './globals.css'

export const metadata = {
  title: '상품 포장 분석기',
  description: '상품을 촬영하여 최적의 포장 사이즈를 추천받으세요',
}

export default function RootLayout({ children }) {
  return (
    <html lang="ko">
      <head>
        <link
          rel="stylesheet"
          as="style"
          crossOrigin="anonymous"
          href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/static/pretendard.min.css"
        />
      </head>
      <body className="font-pretendard">{children}</body>
    </html>
  )
}