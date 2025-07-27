import { clerkMiddleware } from '@clerk/nextjs/server'

export default clerkMiddleware()

export const config = {
  matcher: [
    '/((?!.+\.[\w]+$|_next).*)', // Skip Next.js internals and all static files
    '/(api|trpc)(.*)',
  ],
}
