import { useState } from "react";
import { Info } from "lucide-react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";

export default function ComponentExamples() {
  const [name, setName] = useState("");
  const [error, setError] = useState(false);
  const [message, setMessage] = useState("Nothing submitted.");
  const [confirmOpen, setConfirmOpen] = useState(false);
  return (
    <article className="component-examples">
      <p className="eyebrow">Development reference</p>
      <h1>Shared component examples</h1>
      <p>
        Local examples only. These controls do not create a session or save
        files.
      </p>
      <section className="space-y-4">
        <h2>Button, Input, Label and Select</h2>
        <form
          className="space-y-4"
          onSubmit={(event) => {
            event.preventDefault();
            setError(!name.trim());
            setMessage(
              name.trim()
                ? `Example submitted: ${name.trim()}. Nothing was saved.`
                : "Nothing submitted.",
            );
          }}
        >
          <div className="space-y-2">
            <Label htmlFor="example-name">Example filename</Label>
            <Input
              id="example-name"
              value={name}
              onChange={(event) => setName(event.target.value)}
              aria-invalid={error}
              aria-describedby="name-help"
            />
            <p
              id="name-help"
              className={error ? "text-destructive" : "text-muted-foreground"}
            >
              {error
                ? "Enter a filename. Your input has been kept."
                : "Try submitting an empty value to see a persistent field error."}
            </p>
          </div>
          <div className="space-y-2">
            <Label htmlFor="example-format">Example format</Label>
            <Select
              defaultValue="text"
              items={{ text: "Plain text", python: "Python" }}
            >
              <SelectTrigger id="example-format">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="text">Plain text</SelectItem>
                <SelectItem value="python">Python</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button type="submit">Submit example</Button>
            <Button
              variant="outline"
              type="button"
              onClick={() => {
                setName("");
                setError(false);
                setMessage("Example cleared.");
              }}
            >
              Clear example
            </Button>
            <Button disabled>Disabled</Button>
          </div>
          <p role="status">{message}</p>
        </form>
      </section>
      <section className="space-y-4">
        <h2>Tabs</h2>
        <Tabs defaultValue="usage">
          <TabsList aria-label="Example tabs">
            <TabsTrigger value="usage">Usage</TabsTrigger>
            <TabsTrigger value="keyboard">Keyboard</TabsTrigger>
          </TabsList>
          <TabsContent value="usage">
            Keep temporary panel state local. Use keepMounted for panels
            containing drafts.
          </TabsContent>
          <TabsContent value="keyboard">
            Use arrow keys to focus a tab, Enter or Space to select it, then Tab
            to enter the panel.
          </TabsContent>
        </Tabs>
      </section>
      <section className="space-y-4">
        <h2>Dialog, AlertDialog and Tooltip</h2>
        <div className="flex flex-wrap gap-2">
          <Dialog>
            <DialogTrigger render={<Button variant="outline" />}>
              Open example dialog
            </DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>Example dialog</DialogTitle>
                <DialogDescription>
                  Focus stays inside this dialog. Press Escape to close and
                  return to the trigger.
                </DialogDescription>
              </DialogHeader>
            </DialogContent>
          </Dialog>
          <AlertDialog open={confirmOpen} onOpenChange={setConfirmOpen}>
            <AlertDialogTrigger render={<Button variant="destructive" />}>
              Reset example
            </AlertDialogTrigger>
            <AlertDialogContent>
              <AlertDialogHeader>
                <AlertDialogTitle>Reset this example?</AlertDialogTitle>
                <AlertDialogDescription>
                  This only clears the example filename. Real destructive
                  actions must explain their effect and wait for confirmation.
                </AlertDialogDescription>
              </AlertDialogHeader>
              <AlertDialogFooter>
                <AlertDialogCancel>Cancel</AlertDialogCancel>
                <AlertDialogAction
                  variant="destructive"
                  onClick={() => {
                    setName("");
                    setError(false);
                    setMessage("Example reset. No Workspace was changed.");
                    setConfirmOpen(false);
                  }}
                >
                  Confirm example reset
                </AlertDialogAction>
              </AlertDialogFooter>
            </AlertDialogContent>
          </AlertDialog>
          <Tooltip>
            <TooltipTrigger render={<Button variant="ghost" />}>
              Tooltip example
            </TooltipTrigger>
            <TooltipContent>
              Supplement a visible label; never hide essential instructions
              here.
            </TooltipContent>
          </Tooltip>
        </div>
      </section>
      <Alert>
        <Info aria-hidden="true" />
        <AlertTitle>Persistent feedback</AlertTitle>
        <AlertDescription>
          Keep actionable failures beside the affected control. Do not report
          success until the server confirms it.
        </AlertDescription>
      </Alert>
    </article>
  );
}
