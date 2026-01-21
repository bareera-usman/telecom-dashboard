import './globals.css'

export const metadata = {
  title: 'Vodafone Dashboard - PDF Edition',
  description: 'Telecom invoice analytics with PDF upload',
}

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  )
}
